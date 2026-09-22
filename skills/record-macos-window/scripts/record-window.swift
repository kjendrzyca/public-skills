import AppKit
import AVFoundation
import CoreMedia
import Darwin
import Foundation
import ScreenCaptureKit

@main
enum Program {
    static func main() async {
        guard #available(macOS 15.0, *) else {
            writeError("record-window requires macOS 15 or newer.")
            Foundation.exit(2)
        }

        do {
            let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
            if options.showHelp {
                print(Options.help)
                return
            }
            try await WindowRecorder.run(options: options)
        } catch let error as RecorderError {
            writeError(error.localizedDescription)
            Foundation.exit(Int32(error.exitCode))
        } catch {
            writeError(error.localizedDescription)
            Foundation.exit(1)
        }
    }
}

@available(macOS 15.0, *)
final class RecordingDelegate: NSObject, SCRecordingOutputDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var storedFailure: Error?
    private var storedStarted = false
    private var storedFinished = false

    var failure: Error? {
        lock.withLock { storedFailure }
    }

    var hasStarted: Bool {
        lock.withLock { storedStarted }
    }

    var hasFinished: Bool {
        lock.withLock { storedFinished }
    }

    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) {
        lock.withLock { storedStarted = true }
    }

    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) {
        lock.withLock { storedFailure = error }
    }

    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) {
        lock.withLock { storedFinished = true }
    }
}

struct Options {
    var listWindows = false
    var showHelp = false
    var windowID: CGWindowID?
    var windowTitle: String?
    var ownerName: String?
    var outputPath: String?
    var duration: Double?
    var fps = 60
    var showCursor = true
    var overwrite = false

    static let help = """
    Usage:
      record-window --list-windows --window-title QUERY [--owner-name QUERY]
      record-window --window-id ID --duration SECONDS --output FILE [OPTIONS]
      record-window [--window-title QUERY] [--owner-name QUERY] --duration SECONDS --output FILE [OPTIONS]

    Record one visible macOS window with ScreenCaptureKit at native pixel density.

    Required for recording:
      --window-id ID         Exact window ID from --list-windows; preferred.
      --window-title QUERY   Case-insensitive title substring.
      --duration SECONDS     Recording duration after capture starts.
      --output FILE          Destination MP4 file.

    Options:
      --owner-name QUERY     Case-insensitive owning-application substring.
      --fps NUMBER           Requested maximum frame rate, 1-60. Default: 60.
      --hide-cursor          Hide the pointer. Visible by default.
      --overwrite            Replace an existing output file.
      --list-windows         Print windows matching the required title filter.
      -h, --help             Show this help.

    The raw recording may use variable frame timing. Normalize delivery footage
    with normalize-video.py before claiming exact constant 60 fps.
    """

    static func parse(_ arguments: [String]) throws -> Options {
        var options = Options()
        var index = 0

        func value(after flag: String) throws -> String {
            let valueIndex = index + 1
            guard valueIndex < arguments.count else {
                throw RecorderError.invalidArguments("Missing value after \(flag). Run --help for usage.")
            }
            index = valueIndex
            return arguments[valueIndex]
        }

        while index < arguments.count {
            let argument = arguments[index]
            switch argument {
            case "-h", "--help":
                options.showHelp = true
            case "--list-windows":
                options.listWindows = true
            case "--window-id":
                let rawValue = try value(after: argument)
                guard let windowID = CGWindowID(rawValue), windowID > 0 else {
                    throw RecorderError.invalidArguments("--window-id must be a positive integer. Received: \(rawValue)")
                }
                options.windowID = windowID
            case "--window-title":
                options.windowTitle = try value(after: argument)
            case "--owner-name":
                options.ownerName = try value(after: argument)
            case "--output":
                options.outputPath = try value(after: argument)
            case "--duration":
                let rawValue = try value(after: argument)
                guard let duration = Double(rawValue), duration.isFinite, duration > 0 else {
                    throw RecorderError.invalidArguments("--duration must be a positive number. Received: \(rawValue)")
                }
                options.duration = duration
            case "--fps":
                let rawValue = try value(after: argument)
                guard let fps = Int(rawValue), (1 ... 60).contains(fps) else {
                    throw RecorderError.invalidArguments("--fps must be an integer from 1 to 60. Received: \(rawValue)")
                }
                options.fps = fps
            case "--hide-cursor":
                options.showCursor = false
            case "--overwrite":
                options.overwrite = true
            default:
                throw RecorderError.invalidArguments("Unknown option: \(argument). Run --help for usage.")
            }
            index += 1
        }

        if let title = options.windowTitle, title.isEmpty {
            throw RecorderError.invalidArguments("--window-title cannot be empty.")
        }
        if let owner = options.ownerName, owner.isEmpty {
            throw RecorderError.invalidArguments("--owner-name cannot be empty.")
        }

        if options.showHelp {
            return options
        }

        if options.listWindows {
            guard options.windowTitle != nil else {
                throw RecorderError.invalidArguments(
                    "Window listing can expose private titles. Pass --window-title; --owner-name may additionally narrow the results."
                )
            }
            return options
        }

        if options.windowID == nil {
            guard options.windowTitle != nil || options.ownerName != nil else {
                throw RecorderError.invalidArguments("Pass --window-id, --window-title, or --owner-name. Run --help for usage.")
            }
        }
        guard options.duration != nil else {
            throw RecorderError.invalidArguments("--duration is required. Run --help for usage.")
        }
        guard let outputPath = options.outputPath, !outputPath.isEmpty else {
            throw RecorderError.invalidArguments("--output is required. Run --help for usage.")
        }

        return options
    }
}

@available(macOS 15.0, *)
@MainActor
enum WindowRecorder {
    static func run(options: Options) async throws {
        _ = NSApplication.shared
        let content: SCShareableContent
        do {
            content = try await SCShareableContent.excludingDesktopWindows(
                true,
                onScreenWindowsOnly: true
            )
        } catch {
            throw RecorderError.windowEnumerationFailed(detail: error.localizedDescription)
        }

        if options.listWindows {
            let windows = filteredWindows(
                content.windows,
                title: options.windowTitle,
                owner: options.ownerName
            ).sorted {
                ($0.owningApplication?.applicationName ?? "", $0.title ?? "")
                    < ($1.owningApplication?.applicationName ?? "", $1.title ?? "")
            }
            for window in windows {
                writeJSON([
                    "event": "window",
                    "window_id": Int(window.windowID),
                    "owner": window.owningApplication?.applicationName ?? "Unknown",
                    "title": window.title ?? "",
                    "width_points": Double(window.frame.width),
                    "height_points": Double(window.frame.height),
                ])
            }
            writeJSON(["event": "window-list-complete", "count": windows.count])
            return
        }

        let window: SCWindow
        if let windowID = options.windowID {
            guard let exactWindow = content.windows.first(where: { $0.windowID == windowID }) else {
                throw RecorderError.windowIDNotFound(windowID)
            }
            window = exactWindow
        } else {
            let matches = filteredWindows(
                content.windows,
                title: options.windowTitle,
                owner: options.ownerName
            )
            guard !matches.isEmpty else {
                throw RecorderError.windowNotFound(title: options.windowTitle, owner: options.ownerName)
            }
            guard matches.count == 1, let uniqueWindow = matches.first else {
                throw RecorderError.ambiguousWindowMatch(
                    title: options.windowTitle,
                    owner: options.ownerName,
                    windowIDs: matches.map(\.windowID)
                )
            }
            window = uniqueWindow
        }

        guard let rawOutputPath = options.outputPath else {
            throw RecorderError.invalidArguments("--output is required.")
        }
        let expandedOutputPath = (rawOutputPath as NSString).expandingTildeInPath
        let outputURL = URL(fileURLWithPath: expandedOutputPath).standardizedFileURL
        guard outputURL.pathExtension.lowercased() == "mp4" else {
            throw RecorderError.invalidArguments("--output must use the .mp4 extension.")
        }

        let fileManager = FileManager.default
        try fileManager.createDirectory(
            at: outputURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let initialTarget = try inspectOutputTarget(at: outputURL.path)
        if case .regular = initialTarget, !options.overwrite {
            throw RecorderError.outputExists(path: outputURL.path)
        }

        let temporaryURL = outputURL.deletingLastPathComponent().appendingPathComponent(
            ".\(outputURL.lastPathComponent).recording-\(UUID().uuidString).mp4"
        )
        guard case .absent = try inspectOutputTarget(at: temporaryURL.path) else {
            throw RecorderError.temporaryOutputUnavailable
        }
        var installed = false
        defer {
            if !installed {
                _ = unlink(temporaryURL.path)
            }
        }

        let filter = SCContentFilter(desktopIndependentWindow: window)
        let configuration = SCStreamConfiguration()
        configuration.width = evenPixelDimension(window.frame.width, scale: CGFloat(filter.pointPixelScale))
        configuration.height = evenPixelDimension(window.frame.height, scale: CGFloat(filter.pointPixelScale))
        configuration.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(options.fps))
        configuration.queueDepth = 8
        configuration.captureResolution = .best
        configuration.scalesToFit = false
        configuration.preservesAspectRatio = true
        configuration.ignoreShadowsSingleWindow = true
        configuration.showsCursor = options.showCursor
        configuration.capturesAudio = false

        let outputConfiguration = SCRecordingOutputConfiguration()
        outputConfiguration.outputURL = temporaryURL
        outputConfiguration.videoCodecType = .h264
        outputConfiguration.outputFileType = .mp4

        let delegate = RecordingDelegate()
        let recordingOutput = SCRecordingOutput(
            configuration: outputConfiguration,
            delegate: delegate
        )
        let stream = SCStream(filter: filter, configuration: configuration, delegate: nil)

        try stream.addRecordingOutput(recordingOutput)
        try await stream.startCapture()

        if try await waitForStart(delegate, timeout: .seconds(10)) == false {
            try await stream.stopCapture()
            throw RecorderError.recordingStartTimedOut
        }
        if let failure = delegate.failure {
            try await stream.stopCapture()
            throw failure
        }

        writeJSON([
            "event": "READY",
            "width": configuration.width,
            "height": configuration.height,
            "requested_fps": options.fps,
        ])

        guard let duration = options.duration else {
            throw RecorderError.invalidArguments("--duration is required.")
        }
        try await Task.sleep(for: .seconds(duration))
        try stream.removeRecordingOutput(recordingOutput)

        if try await waitForFinish(delegate, timeout: .seconds(10)) == false {
            try await stream.stopCapture()
            throw RecorderError.recordingFinishTimedOut
        }
        try await stream.stopCapture()
        if let failure = delegate.failure {
            throw failure
        }

        try installTemporaryOutput(
            temporaryURL,
            at: outputURL,
            initialTarget: initialTarget
        )
        installed = true

        writeJSON([
            "event": "recording-finished",
            "duration_seconds": duration,
            "bytes": recordingOutput.recordedFileSize,
        ])
    }

    private static func evenPixelDimension(_ points: CGFloat, scale: CGFloat) -> Int {
        let pixels = max(2, Int((points * scale).rounded()))
        return pixels.isMultiple(of: 2) ? pixels : pixels - 1
    }

    private static func filteredWindows(
        _ windows: [SCWindow],
        title: String?,
        owner: String?
    ) -> [SCWindow] {
        windows.filter { window in
            if let title,
               !(window.title ?? "").localizedCaseInsensitiveContains(title)
            {
                return false
            }
            if let owner,
               !(window.owningApplication?.applicationName ?? "")
                   .localizedCaseInsensitiveContains(owner)
            {
                return false
            }
            return true
        }
    }

    private static func inspectOutputTarget(at path: String) throws -> OutputTarget {
        var information = stat()
        if lstat(path, &information) == 0 {
            let fileType = information.st_mode & S_IFMT
            if fileType == S_IFLNK {
                throw RecorderError.unsafeOutputTarget(path: path, kind: "symbolic link")
            }
            guard fileType == S_IFREG else {
                throw RecorderError.unsafeOutputTarget(path: path, kind: "non-regular file")
            }
            return .regular(
                FileIdentity(
                    device: UInt64(information.st_dev),
                    inode: UInt64(information.st_ino)
                )
            )
        }

        let errorNumber = errno
        if errorNumber == ENOENT {
            return .absent
        }
        throw RecorderError.outputInspectionFailed(
            path: path,
            detail: String(cString: strerror(errorNumber))
        )
    }

    private static func installTemporaryOutput(
        _ temporaryURL: URL,
        at outputURL: URL,
        initialTarget: OutputTarget
    ) throws {
        let currentTarget = try inspectOutputTarget(at: outputURL.path)
        guard currentTarget == initialTarget else {
            throw RecorderError.outputChangedDuringRecording(path: outputURL.path)
        }
        if rename(temporaryURL.path, outputURL.path) != 0 {
            throw RecorderError.outputInstallFailed(
                path: outputURL.path,
                detail: String(cString: strerror(errno))
            )
        }
    }

    private static func waitForStart(
        _ delegate: RecordingDelegate,
        timeout: Duration
    ) async throws -> Bool {
        try await waitUntil(timeout: timeout) {
            delegate.hasStarted || delegate.failure != nil
        }
    }

    private static func waitForFinish(
        _ delegate: RecordingDelegate,
        timeout: Duration
    ) async throws -> Bool {
        try await waitUntil(timeout: timeout) {
            delegate.hasFinished || delegate.failure != nil
        }
    }

    private static func waitUntil(
        timeout: Duration,
        predicate: @escaping @Sendable () -> Bool
    ) async throws -> Bool {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        while clock.now < deadline {
            if predicate() {
                return true
            }
            try await Task.sleep(for: .milliseconds(50))
        }
        return predicate()
    }
}

struct FileIdentity: Equatable {
    let device: UInt64
    let inode: UInt64
}

enum OutputTarget: Equatable {
    case absent
    case regular(FileIdentity)
}

enum RecorderError: LocalizedError {
    case invalidArguments(String)
    case ambiguousWindowMatch(title: String?, owner: String?, windowIDs: [CGWindowID])
    case outputChangedDuringRecording(path: String)
    case outputExists(path: String)
    case outputInspectionFailed(path: String, detail: String)
    case outputInstallFailed(path: String, detail: String)
    case recordingFinishTimedOut
    case recordingStartTimedOut
    case temporaryOutputUnavailable
    case unsafeOutputTarget(path: String, kind: String)
    case windowEnumerationFailed(detail: String)
    case windowIDNotFound(CGWindowID)
    case windowNotFound(title: String?, owner: String?)

    var exitCode: Int {
        switch self {
        case .invalidArguments:
            return 2
        case .ambiguousWindowMatch, .windowIDNotFound, .windowNotFound:
            return 4
        case .outputExists, .unsafeOutputTarget:
            return 5
        case .outputChangedDuringRecording, .outputInspectionFailed, .outputInstallFailed,
             .recordingFinishTimedOut, .recordingStartTimedOut, .temporaryOutputUnavailable,
             .windowEnumerationFailed:
            return 1
        }
    }

    var errorDescription: String? {
        switch self {
        case let .invalidArguments(message):
            return message
        case let .ambiguousWindowMatch(title, owner, windowIDs):
            let ids = windowIDs.map(String.init).joined(separator: ", ")
            return "\(windowFilterDescription(title: title, owner: owner)) matched \(windowIDs.count) visible windows (IDs: \(ids)). Choose one with --window-id."
        case let .outputChangedDuringRecording(path):
            return "Output target changed while recording: \(path). The finalized temporary recording was not installed."
        case let .outputExists(path):
            return "Output already exists: \(path). Pass --overwrite only when replacement is intended."
        case let .outputInspectionFailed(path, detail):
            return "Could not inspect output target \(path): \(detail)"
        case let .outputInstallFailed(path, detail):
            return "Could not atomically install the finalized recording at \(path): \(detail)"
        case .recordingFinishTimedOut:
            return "Timed out while finalizing the MP4. Keep the source file for inspection before retrying."
        case .recordingStartTimedOut:
            return "Timed out while starting capture. Check Screen Recording permission and rerun --list-windows."
        case .temporaryOutputUnavailable:
            return "Could not reserve a private temporary recording path. Retry the command."
        case let .unsafeOutputTarget(path, kind):
            return "Output target is a \(kind): \(path). Use an absent path or a regular file with --overwrite."
        case let .windowEnumerationFailed(detail):
            return "Could not list visible windows: \(detail). Grant Screen Recording permission to the terminal or agent host, restart it, and retry."
        case let .windowIDNotFound(windowID):
            return "No visible window has ID \(windowID). Run --list-windows again because window IDs change when windows reopen."
        case let .windowNotFound(title, owner):
            return "No visible window matched \(windowFilterDescription(title: title, owner: owner)). Run a filtered --list-windows query and choose an exact ID."
        }
    }
}

func windowFilterDescription(title: String?, owner: String?) -> String {
    var filters: [String] = []
    if let title {
        filters.append("title containing '\(title)'")
    }
    if let owner {
        filters.append("owner containing '\(owner)'")
    }
    return filters.isEmpty ? "the requested filters" : filters.joined(separator: " and ")
}

func writeJSON(_ object: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else {
        return
    }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([0x0A]))
}

func writeError(_ message: String) {
    FileHandle.standardError.write(Data("Error: \(message)\n".utf8))
}
