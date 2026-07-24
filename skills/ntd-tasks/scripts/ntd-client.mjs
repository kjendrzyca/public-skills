#!/usr/bin/env node

import { randomUUID, webcrypto } from 'node:crypto'
import { realpathSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const crypto = webcrypto

const TOKEN_PREFIX = 'ntd_'
const TASKS_PER_DAY_LIMIT = 5
const SHORT_ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

const padDatePart = (value) => String(value).padStart(2, '0')

export const isShortIsoDate = (value) => SHORT_ISO_DATE_PATTERN.test(value)

// Tasks synced by pre-calendar-day app versions store days as full ISO
// instants that meant "local midnight in the timezone the data was created
// in". The app's codec interprets those in Europe/Warsaw; the CLI must apply
// the same rule, otherwise view filters and the 5-task daily limit disagree
// with the app for exactly the legacy records. New inputs from the agent are
// still interpreted in the machine's local timezone (see toLocalDateKey).
const LEGACY_DATA_TIMEZONE = 'Europe/Warsaw'

const legacyInstantToDateKey = (value) => {
  const instant = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(instant.getTime())) {
    return null
  }

  return new Intl.DateTimeFormat('en-CA', {
    timeZone: LEGACY_DATA_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(instant)
}

// Single choke point for legacy payload shapes: every decrypted task is
// normalized to calendar-day strings before any filtering, validation,
// update, or output sees it. Mirrors src/encryption/taskCodec.ts.
export const normalizeDecryptedTask = (task) => {
  const normalized = { ...task }

  if (normalized.date && !isShortIsoDate(normalized.date)) {
    normalized.date = legacyInstantToDateKey(normalized.date)
  }

  if (normalized.completedOn === undefined && normalized.completedAt) {
    normalized.completedOn = legacyInstantToDateKey(normalized.completedAt)
    normalized.completedAt = null
  } else if (normalized.completedOn && !isShortIsoDate(normalized.completedOn)) {
    normalized.completedOn = legacyInstantToDateKey(normalized.completedOn)
  }

  return normalized
}

export const toLocalDateKey = (value) => {
  if (!value) {
    return null
  }

  if (typeof value === 'string' && isShortIsoDate(value)) {
    return value
  }

  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid date: ${value}`)
  }

  return `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`
}

// Scheduled days are stored as plain calendar-day strings ('yyyy-MM-dd'),
// matching the app's task model. Full ISO inputs resolve to the local
// calendar day of that instant on this machine.
export const normalizeScheduledDateInput = (value) => {
  if (value === null || value === undefined || value === '') {
    return null
  }

  if (typeof value === 'string' && isShortIsoDate(value)) {
    return value
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid date: ${value}`)
  }

  return toLocalDateKey(date)
}

export const isTodayDateString = (dateStr, now = new Date()) => {
  return toLocalDateKey(dateStr) === toLocalDateKey(now)
}

export const isFutureDateString = (dateStr, now = new Date()) => {
  const taskDateKey = toLocalDateKey(dateStr)
  const todayKey = toLocalDateKey(now)
  return taskDateKey !== null && todayKey !== null && taskDateKey > todayKey
}

export const countScheduledTasksForDate = (tasks, dateValue, excludeTaskId) => {
  const dateKey = toLocalDateKey(dateValue)

  if (!dateKey) {
    return 0
  }

  return tasks.filter(
    (task) => !task.deleted && task.id !== excludeTaskId && toLocalDateKey(task.date) === dateKey,
  ).length
}

export const validateTaskLimit = (tasks, dateValue, excludeTaskId) => {
  const tasksCount = countScheduledTasksForDate(tasks, dateValue, excludeTaskId)

  if (tasksCount >= TASKS_PER_DAY_LIMIT) {
    throw new Error(
      `You can only have ${TASKS_PER_DAY_LIMIT} tasks per day. This day already has ${tasksCount} tasks.`,
    )
  }
}

export const shouldTaskStayCompleted = (task, newDateValue, now = new Date()) => {
  if (!task.completed || !newDateValue) {
    return task.completed
  }

  const newDateKey = toLocalDateKey(newDateValue)
  const todayKey = toLocalDateKey(now)

  if (!task.date) {
    return newDateKey < todayKey
  }

  const previousDateKey = toLocalDateKey(task.date)
  return previousDateKey === newDateKey || newDateKey < todayKey
}

export const shouldValidateTaskLimit = (existingTask, updatedTask) => {
  const previousDateKey = existingTask.deleted ? null : toLocalDateKey(existingTask.date)
  const nextDateKey = updatedTask.deleted ? null : toLocalDateKey(updatedTask.date)

  if (!nextDateKey) {
    return false
  }

  if (!previousDateKey) {
    return true
  }

  return previousDateKey !== nextDateKey
}

export const applyTaskUpdate = (existingTask, input, nowIso = new Date().toISOString()) => {
  // completedAt is a read-only legacy field (old app versions); never accept
  // it as update input
  const { completedAt: _ignoredLegacyInput, ...sanitizedInput } = input

  const updatedTask = {
    ...existingTask,
    ...sanitizedInput,
    lastUpdatedAt: nowIso,
  }

  if (Object.prototype.hasOwnProperty.call(input, 'date')) {
    updatedTask.date = normalizeScheduledDateInput(input.date)

    if (!Object.prototype.hasOwnProperty.call(input, 'completed')) {
      updatedTask.completed = shouldTaskStayCompleted(
        existingTask,
        updatedTask.date,
        new Date(nowIso),
      )

      if (!updatedTask.completed) {
        updatedTask.completedOn = null
        updatedTask.completedAt = null
      }
    }
  }

  if (Object.prototype.hasOwnProperty.call(input, 'completed')) {
    if (input.completed) {
      updatedTask.completed = true
      // Recover the day from a legacy completedAt instant before falling back
      // to today, so re-completing an already-completed legacy record does not
      // rewrite history
      updatedTask.completedOn =
        input.completedOn ??
        existingTask.completedOn ??
        (existingTask.completed && existingTask.completedAt
          ? toLocalDateKey(new Date(existingTask.completedAt))
          : toLocalDateKey(new Date(nowIso)))
    } else {
      updatedTask.completed = false
      updatedTask.completedOn = null
    }
    // Legacy completion instant: never carried forward on writes
    updatedTask.completedAt = null
  } else if (Object.prototype.hasOwnProperty.call(input, 'completedOn')) {
    updatedTask.completedOn = input.completedOn
  }

  return updatedTask
}

const decodeBase64Url = (value) => {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  return Buffer.from(`${base64}${padding}`, 'base64').toString('utf8')
}

const parseToken = (token) => {
  if (!token.startsWith(TOKEN_PREFIX)) {
    throw new Error(`Invalid token format: must start with ${TOKEN_PREFIX}`)
  }

  const payload = JSON.parse(decodeBase64Url(token.slice(TOKEN_PREFIX.length)))

  if (
    payload?.v !== 1 ||
    typeof payload?.serverUrl !== 'string' ||
    typeof payload?.agentAuthToken !== 'string' ||
    typeof payload?.encryptionKey !== 'string'
  ) {
    throw new Error('Invalid token format: missing required fields')
  }

  return payload
}

const readTokenFromStdin = async () => {
  const chunks = []

  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
  }

  const token = Buffer.concat(chunks).toString('utf8').trim()
  return token || null
}

const readRawToken = async () => {
  if (!process.stdin.isTTY) {
    return readTokenFromStdin()
  }

  return null
}

const apiGet = async (serverUrl, procedure, authHeader) => {
  const response = await fetch(`${serverUrl}/api/${procedure}`, {
    headers: { Authorization: authHeader },
  })

  const json = await response.json()
  if (json.error) {
    throw new Error(json.error.json?.message ?? `API error: ${procedure}`)
  }

  return json.result.data
}

const apiPost = async (serverUrl, procedure, body, authHeader) => {
  const response = await fetch(`${serverUrl}/api/${procedure}`, {
    method: 'POST',
    headers: {
      Authorization: authHeader,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  const json = await response.json()
  if (json.error) {
    throw new Error(json.error.json?.message ?? `API error: ${procedure}`)
  }

  return json.result.data
}

const importKey = async (base64Key) => {
  const keyBytes = Buffer.from(base64Key, 'base64')
  return crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, [
    'encrypt',
    'decrypt',
  ])
}

const decrypt = async (key, ciphertext, iv) => {
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: Buffer.from(iv, 'base64') },
    key,
    Buffer.from(ciphertext, 'base64'),
  )

  return new TextDecoder().decode(decrypted)
}

const encrypt = async (key, plaintext) => {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(plaintext),
  )

  return {
    ciphertext: Buffer.from(ciphertext).toString('base64'),
    iv: Buffer.from(iv).toString('base64'),
  }
}

const decryptTask = async (key, envelope) => {
  const json = await decrypt(key, envelope.ciphertext, envelope.iv)
  const payload = JSON.parse(json)
  payload.lastUpdatedAt = envelope.lastUpdatedAt
  return normalizeDecryptedTask(payload)
}

const encryptTask = async (key, task, keyVersion) => {
  const json = JSON.stringify(task)
  const { ciphertext, iv } = await encrypt(key, json)

  return {
    id: task.id,
    ciphertext,
    iv,
    lastUpdatedAt: task.lastUpdatedAt,
    keyVersion,
  }
}

export const filterByView = (tasks, view, now = new Date()) => {
  switch (view) {
    case 'inbox':
      return tasks.filter((task) => !task.completed && !task.date)
    case 'today':
      return tasks.filter(
        (task) => !task.completed && task.date && isTodayDateString(task.date, now),
      )
    case 'upcoming':
      return tasks.filter(
        (task) => !task.completed && task.date && isFutureDateString(task.date, now),
      )
    case 'archive':
      return tasks.filter((task) => task.completed)
    default:
      throw new Error('Unknown view: use inbox, today, upcoming, or archive')
  }
}

const buildTaskForCreate = (input, existingTasks, nowIso) => {
  const normalizedDate = normalizeScheduledDateInput(input.date)
  const nextOrder =
    existingTasks.reduce((maxOrder, task) => Math.max(maxOrder, task.order ?? 0), 0) + 1

  if (normalizedDate) {
    validateTaskLimit(existingTasks, normalizedDate)
  }

  return {
    id: randomUUID(),
    title: input.title,
    description: input.description,
    date: normalizedDate,
    completed: false,
    createdAt: nowIso,
    lastUpdatedAt: nowIso,
    completedOn: null,
    order: nextOrder,
    deleted: false,
  }
}

const getAllDecryptedTasks = async (serverUrl, authHeader, cryptoKey) => {
  const envelopes = await apiGet(serverUrl, 'getTasks', authHeader)
  const tasks = []

  for (const envelope of envelopes) {
    try {
      const task = await decryptTask(cryptoKey, envelope)
      tasks.push(task)
    } catch (error) {
      process.stderr.write(
        `Warning: Failed to decrypt task ${envelope.id}: ${error instanceof Error ? error.message : 'unknown error'}\n`,
      )
    }
  }

  return tasks
}

const getCurrentKeyVersion = async (serverUrl, authHeader) => {
  const response = await apiGet(serverUrl, 'getCurrentKeyVersion', authHeader)
  return response.keyVersion
}

const cmdList = async (token, cryptoKey, authHeader, args) => {
  const viewIndex = args.indexOf('--view')
  const view = viewIndex >= 0 ? args[viewIndex + 1] : null
  const tasks = await getAllDecryptedTasks(token.serverUrl, authHeader, cryptoKey)
  const visibleTasks = tasks.filter((task) => !task.deleted)
  const filteredTasks = view
    ? filterByView(visibleTasks, view)
    : visibleTasks.filter((task) => !task.completed)

  filteredTasks.sort((left, right) => left.order - right.order)
  process.stdout.write(`${JSON.stringify(filteredTasks, null, 2)}\n`)
}

const cmdCreate = async (token, cryptoKey, authHeader, args) => {
  if (!args[0]) {
    throw new Error('Usage: create \'{"title":"..."}\'')
  }

  const input = JSON.parse(args[0])
  if (!input.title) {
    throw new Error('Task title is required')
  }

  const keyVersion = await getCurrentKeyVersion(token.serverUrl, authHeader)
  const existingTasks = await getAllDecryptedTasks(token.serverUrl, authHeader, cryptoKey)
  const task = buildTaskForCreate(input, existingTasks, new Date().toISOString())

  const envelope = await encryptTask(cryptoKey, task, keyVersion)
  const result = await apiPost(token.serverUrl, 'syncTasks', [envelope], authHeader)
  const createdTask = result.synced[0] ? await decryptTask(cryptoKey, result.synced[0]) : task
  process.stdout.write(`${JSON.stringify(createdTask, null, 2)}\n`)
}

const cmdUpdate = async (token, cryptoKey, authHeader, args) => {
  if (!args[0]) {
    throw new Error('Usage: update \'{"id":"..."}\'')
  }

  const input = JSON.parse(args[0])
  if (!input.id) {
    throw new Error('Task id is required')
  }

  const keyVersion = await getCurrentKeyVersion(token.serverUrl, authHeader)
  const existingTasks = await getAllDecryptedTasks(token.serverUrl, authHeader, cryptoKey)
  const existingTask = existingTasks.find((task) => task.id === input.id)

  if (!existingTask) {
    throw new Error(`Task not found: ${input.id}`)
  }

  const updatedTask = applyTaskUpdate(existingTask, input)

  if (shouldValidateTaskLimit(existingTask, updatedTask)) {
    validateTaskLimit(existingTasks, updatedTask.date, updatedTask.id)
  }

  const envelope = await encryptTask(cryptoKey, updatedTask, keyVersion)
  const result = await apiPost(token.serverUrl, 'syncTasks', [envelope], authHeader)

  if (result.synced.length > 0) {
    const syncedTask = await decryptTask(cryptoKey, result.synced[0])
    process.stdout.write(`${JSON.stringify(syncedTask, null, 2)}\n`)
    return
  }

  if (result.conflicts.length > 0) {
    const conflictTask = await decryptTask(cryptoKey, result.conflicts[0])
    process.stderr.write('Conflict: server version is newer. Returning server version.\n')
    process.stdout.write(`${JSON.stringify(conflictTask, null, 2)}\n`)
  }
}

const cmdComplete = async (token, cryptoKey, authHeader, args) => {
  const taskId = args[0]
  if (!taskId) {
    throw new Error('Usage: complete <task-id>')
  }

  // No explicit completedOn: applyTaskUpdate preserves the existing completion
  // day of an already-completed task (a retried `complete` must not rewrite
  // history) and falls back to today only for a fresh completion
  await cmdUpdate(token, cryptoKey, authHeader, [JSON.stringify({ id: taskId, completed: true })])
}

const cmdDelete = async (token, cryptoKey, authHeader, args) => {
  const taskId = args[0]
  if (!taskId) {
    throw new Error('Usage: delete <task-id>')
  }

  await cmdUpdate(token, cryptoKey, authHeader, [JSON.stringify({ id: taskId, deleted: true })])
}

const main = async () => {
  const rawToken = await readRawToken()
  if (!rawToken) {
    process.stderr.write('Error: No agent token found. Add one to Keychain and try again.\n')
    process.exit(1)
  }

  const token = parseToken(rawToken)
  const cryptoKey = await importKey(token.encryptionKey)
  const authHeader = `Bearer ${token.agentAuthToken}`
  const [command, ...args] = process.argv.slice(2)

  switch (command) {
    case 'list':
      await cmdList(token, cryptoKey, authHeader, args)
      break
    case 'create':
      await cmdCreate(token, cryptoKey, authHeader, args)
      break
    case 'update':
      await cmdUpdate(token, cryptoKey, authHeader, args)
      break
    case 'complete':
      await cmdComplete(token, cryptoKey, authHeader, args)
      break
    case 'delete':
      await cmdDelete(token, cryptoKey, authHeader, args)
      break
    default:
      process.stderr.write(
        'Usage: ntd-client.mjs <command> [args]\n\nCommands:\n  list [--view inbox|today|upcoming|archive]\n  create \'{"title":"...","date":"..."}\'\n  update \'{"id":"...","title":"..."}\'\n  complete <task-id>\n  delete <task-id>\n',
      )
      process.exit(1)
  }
}

const isExecutedDirectly =
  process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))

if (isExecutedDirectly) {
  main().catch((error) => {
    process.stderr.write(`Error: ${error instanceof Error ? error.message : 'Unknown error'}\n`)
    process.exit(1)
  })
}
