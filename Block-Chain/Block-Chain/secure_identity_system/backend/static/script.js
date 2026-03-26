const API_BASE = "/api"

const page = document.body.dataset.page
let headerCondensed = false

const qs = (selector, root = document) => root.querySelector(selector)

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")

async function requestJson(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) }
  
  const token = localStorage.getItem("si_token")
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers: headers,
    ...options,
  })

  const rawText = await response.text()
  const payload = (() => {
    try {
      return JSON.parse(rawText)
    } catch {
      return { message: `Server returned a non-JSON response (HTTP ${response.status}).` }
    }
  })()

  if (!response.ok) {
    const error = new Error(payload.message || "Request failed.")
    error.payload = payload
    throw error
  }

  return payload
}

async function requestFormData(path, formData, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = localStorage.getItem("si_token")
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: formData,
  })

  const payload = await response
    .json()
    .catch(() => ({ message: "Server returned an unreadable response." }))

  if (!response.ok) {
    const error = new Error(payload.message || "Request failed.")
    error.payload = payload
    throw error
  }

  return payload
}

async function requestBlob(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = localStorage.getItem("si_token")
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })

  if (!response.ok) {
    const rawText = await response.text().catch(() => "")
    const payload = (() => {
      try {
        return JSON.parse(rawText)
      } catch {
        return { message: `Download failed (HTTP ${response.status}).` }
      }
    })()
    const error = new Error(payload.message || "Download failed.")
    error.payload = payload
    throw error
  }

  const blob = await response.blob()
  const disposition = response.headers.get("content-disposition") || ""
  return { blob, disposition, contentType: response.headers.get("content-type") || "" }
}

function formatDate(value) {
  if (!value) {
    return "Never"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

function formatClock(value = new Date()) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(value)
}

function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "--"
  }
  return `${value}${suffix}`
}

function toBadgeTone(state) {
  const normalized = String(state || "")
    .trim()
    .toLowerCase()
    .replaceAll(" ", "_")

  if (["synced", "success", "ready", "online", "active"].includes(normalized)) {
    return "success"
  }
  if (["offline", "missing", "mismatch", "error", "not_connected", "not-connected", "disconnected"].includes(normalized)) {
    return "error"
  }
  if (["pending", "usable", "warning"].includes(normalized)) {
    return "warning"
  }
  return "neutral"
}

function humanizeState(value) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function setStatus(element, message, tone = "neutral") {
  if (!element) {
    return
  }
  element.textContent = message
  element.className = `status-panel is-${tone}`
}

function setBadge(element, message, tone = "neutral") {
  if (!element) {
    return
  }
  element.textContent = message
  element.className = `badge ${tone}`
}

function setMetric(name, value) {
  document.querySelectorAll(`[data-metric="${name}"]`).forEach((element) => {
    element.textContent = value
  })
}

function isReloadNavigation() {
  const navigationEntry = performance.getEntriesByType?.("navigation")?.[0]
  if (navigationEntry) {
    return navigationEntry.type === "reload"
  }
  return performance.navigation?.type === 1
}

function redirectReloadToHome() {
  if (window.location.pathname === "/") {
    return
  }
  if (!isReloadNavigation()) {
    return
  }
  window.location.replace("/")
}

function syncHeaderShell() {
  const headerShell = qs(".site-header-shell")
  if (!headerShell) {
    return
  }

  const collapseAt = 48
  const expandAt = 20

  if (!headerCondensed && window.scrollY > collapseAt) {
    headerCondensed = true
  } else if (headerCondensed && window.scrollY < expandAt) {
    headerCondensed = false
  }

  headerShell.classList.toggle("is-condensed", headerCondensed)
}

function syncHomeHero() {
  const heroShell = qs("#home-hero")
  if (!heroShell) {
    return
  }

  const progress = Math.min(window.scrollY / 260, 1)
  heroShell.style.setProperty("--hero-progress", progress.toFixed(3))
  heroShell.classList.toggle("is-condensed", progress > 0.08)
}

function describeCameraError(error) {
  switch (error?.name) {
    case "NotAllowedError":
      return {
        tone: "error",
        badge: "Permission denied",
        message: "Camera access was denied. Allow camera permission for 127.0.0.1 and try again.",
      }
    case "NotFoundError":
      return {
        tone: "error",
        badge: "No camera",
        message: "No camera device was found on this machine.",
      }
    case "NotReadableError":
      return {
        tone: "error",
        badge: "Camera busy",
        message: "The camera is already in use by another tab or app. Close it there, then try again.",
      }
    case "SecurityError":
      return {
        tone: "error",
        badge: "Blocked by browser",
        message: "The browser blocked camera access for this page.",
      }
    case "AbortError":
      return {
        tone: "error",
        badge: "Camera interrupted",
        message: "Camera startup was interrupted. Try starting it again.",
      }
    default:
      return {
        tone: "error",
        badge: "Camera unavailable",
        message: "Unable to access the camera. Check permissions, device access, or other active camera apps.",
      }
  }
}

function renderChainSummary(blockchain) {
  const indicator = qs("[data-chain-indicator]")
  const text = qs("[data-chain-text]")
  if (indicator) {
    indicator.className = `status-dot ${blockchain?.ready ? "online" : "offline"}`
  }
  if (text) {
    text.textContent = blockchain?.ready
      ? "Connected and ready for verification"
      : blockchain?.last_error || "Blockchain not ready"
  }

  const chainBadge = qs("#dashboard-chain-badge")
  if (chainBadge) {
    setBadge(chainBadge, humanizeState(blockchain?.ready ? "ready" : "offline"), toBadgeTone(blockchain?.ready ? "ready" : "offline"))
  }

  const rpcUrl = qs("#dashboard-rpc-url")
  const contractAddress = qs("#dashboard-contract-address")
  const account = qs("#dashboard-account")
  const chainError = qs("#dashboard-chain-error")

  if (rpcUrl) {
    rpcUrl.textContent = blockchain?.rpc_url || "--"
  }
  if (contractAddress) {
    contractAddress.textContent = blockchain?.contract_address || "Not configured"
  }
  if (account) {
    account.textContent = blockchain?.account || "Unavailable"
  }
  if (chainError) {
    chainError.textContent = blockchain?.last_error || "None"
  }
}

function renderOverviewMetrics(metrics) {
  setMetric("total-users", formatNumber(metrics.total_users))
  setMetric("success-rate", formatNumber(metrics.success_rate, "%"))
  setMetric("quality", formatNumber(metrics.average_quality))
  setMetric("synced-users", formatNumber(metrics.synced_users))
}

function renderQuality(prefix, quality) {
  const label = qs(`#${prefix}-quality-label`)
  const score = qs(`#${prefix}-quality-score`)
  const fill = qs(`#${prefix}-quality-fill`)
  const issues = qs(`#${prefix}-quality-issues`)

  if (!quality) {
    if (label) {
      label.textContent = "No capture yet"
    }
    if (score) {
      score.textContent = "--"
    }
    if (fill) {
      fill.style.width = "4%"
    }
    if (issues) {
      issues.innerHTML = "<li>Capture a frame to analyze blur, lighting, and framing.</li>"
    }
    return
  }

  if (label) {
    label.textContent = `${quality.label}${quality.ready ? " - ready" : ""}`
  }
  if (score) {
    score.textContent = quality.score
  }
  if (fill) {
    fill.style.width = `${Math.max(4, quality.score)}%`
  }
  if (issues) {
    const details = quality.issues.length
      ? quality.issues
      : [
          `Blur ${quality.metrics.blur_score}, brightness ${quality.metrics.brightness}, face ratio ${quality.metrics.face_ratio}.`,
        ]
    issues.innerHTML = details.map((issue) => `<li>${escapeHtml(issue)}</li>`).join("")
  }
}

function stopStream(stream) {
  if (!stream) {
    return
  }
  stream.getTracks().forEach((track) => track.stop())
}

async function startCamera(videoElement) {
  return navigator.mediaDevices.getUserMedia({
    video: {
      width: { ideal: 1280 },
      height: { ideal: 720 },
      facingMode: "user",
    },
    audio: false,
  }).then((stream) => {
    videoElement.srcObject = stream
    return stream
  })
}

function captureFrame(videoElement, canvasElement) {
  const context = canvasElement.getContext("2d")
  canvasElement.width = videoElement.videoWidth
  canvasElement.height = videoElement.videoHeight
  context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height)
  return canvasElement.toDataURL("image/jpeg", 0.95)
}

function renderResultPanel(element, html) {
  if (element) {
    element.innerHTML = html
  }
}

function renderResponseCard(payload, mode) {
  if (mode === "register" || mode === "admin-register") {
    const isPending = Boolean(payload.pending_approval)
    const txHash = payload.blockchain?.tx_hash
      ? `<div><strong>Transaction</strong><div class="mono">${escapeHtml(payload.blockchain.tx_hash)}</div></div>`
      : ""
    
    return `
      <div class="response-grid">
        <strong style="${isPending ? 'color: var(--warning-color);' : ''}">${escapeHtml(payload.message)}</strong>
        <div class="response-chip-row">
          <span class="response-chip">Quality ${escapeHtml(payload.quality?.label || "Good")} / ${escapeHtml(payload.quality?.score || "95")}</span>
          <span class="response-chip">Status ${isPending ? "Pending Approval" : "Live"}</span>
        </div>
        ${payload.user ? `
          <div><strong>User</strong><div>${escapeHtml(payload.user.name)} (${escapeHtml(payload.user.email)})</div></div>
          <div><strong>Identity hash</strong><div class="mono">${escapeHtml(payload.user.identity_hash)}</div></div>
        ` : ""}
        ${txHash}
      </div>
    `
  }

  return `
    <div class="response-grid">
      <strong>${escapeHtml(payload.message)}</strong>
      <div class="response-chip-row">
        <span class="response-chip">Confidence ${escapeHtml(payload.match.confidence)}%</span>
        <span class="response-chip">Distance ${escapeHtml(payload.match.distance)}</span>
        <span class="response-chip">Verification ${escapeHtml(humanizeState(payload.verification.state))}</span>
      </div>
      <div><strong>User</strong><div>${escapeHtml(payload.user.name)} (${escapeHtml(payload.user.email)})</div></div>
      <div><strong>Local hash</strong><div class="mono">${escapeHtml(payload.verification.local_hash)}</div></div>
      <div><strong>Chain hash</strong><div class="mono">${escapeHtml(payload.verification.chain_hash || "Not available")}</div></div>
    </div>
  `
}

function initCaptureWorkflow(prefix, endpoint, bodyBuilder) {
  const video = qs(`#${prefix}-video`)
  const canvas = qs(`#${prefix}-canvas`)
  const preview = qs(`#${prefix}-preview`)
  const previewCard = preview?.closest(".preview-card")
  const startButton = qs(`#${prefix}-start`)
  const captureButton = qs(`#${prefix}-capture`)
  const retakeButton = qs(`#${prefix}-retake`)
  const stopButton = qs(`#${prefix}-stop`)
  const form = qs(`#${prefix}-form`)
  const status = qs(`#${prefix}-status`)
  const result = qs(`#${prefix}-result`)
  const cameraState = qs(`#${prefix}-camera-state`)

  const state = {
    stream: null,
    captureData: null,
    analysis: null,
    releasedInBackground: false,
  }

  function setPreviewState(hasImage) {
    if (!previewCard) {
      return
    }
    previewCard.classList.toggle("is-empty", !hasImage)
  }

  function resetCaptureState() {
    state.captureData = null
    state.analysis = null
    preview.removeAttribute("src")
    preview.alt = "No capture yet"
    setPreviewState(false)
    renderQuality(prefix, null)
  }

  function stopCamera(options = {}) {
    const { silent = false, reason = "Camera stopped.", tone = "neutral", badge = "Camera idle" } = options
    stopStream(state.stream)
    state.stream = null
    video.srcObject = null
    setBadge(cameraState, badge, tone === "success" ? "success" : "neutral")
    if (!silent) {
      setStatus(status, reason, tone)
    }
  }

  async function handleStartCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(status, "Camera access is not supported in this browser.", "error")
      setBadge(cameraState, "Unsupported", "error")
      return
    }

    try {
      if (state.stream) {
        setStatus(status, "Camera is already running.", "neutral")
        return
      }
      state.stream = await startCamera(video)
      setStatus(status, "Camera ready. Capture a frame when the face is centered.", "neutral")
      setBadge(cameraState, "Camera live", "success")
    } catch (error) {
      const cameraError = describeCameraError(error)
      setStatus(status, cameraError.message, cameraError.tone)
      setBadge(cameraState, cameraError.badge, cameraError.tone)
    }
  }

  async function handleCapture() {
    if (!state.stream) {
      setStatus(status, "Start the camera before capturing.", "error")
      return
    }
    if (!video.videoWidth || !video.videoHeight) {
      setStatus(status, "Camera is still warming up. Try again in a moment.", "error")
      return
    }

    state.captureData = captureFrame(video, canvas)
    preview.src = state.captureData
    preview.alt = "Captured face preview"
    setPreviewState(true)
    setStatus(status, "Analyzing capture quality...", "neutral")

    try {
      const analysisPayload = await requestJson("/analyze-capture", {
        method: "POST",
        body: JSON.stringify({ image: state.captureData }),
      })
      state.analysis = analysisPayload.quality
      renderQuality(prefix, state.analysis)
      setStatus(
        status,
        state.analysis.ready
          ? "Capture cleared the quality gate."
          : "Capture needs improvement before submission.",
        state.analysis.ready ? "success" : "error"
      )
    } catch (error) {
      setStatus(status, error.payload?.message || "Failed to analyze capture.", "error")
    }
  }

  function handleRetake() {
    resetCaptureState()
    setStatus(status, "Capture cleared. Take a new frame when ready.", "neutral")
  }

  function handleStop() {
    stopCamera()
  }

async function handleSubmit(event) {
    event.preventDefault()

    if (!state.captureData) {
      setStatus(status, "Capture a face image before continuing.", "error")
      return
    }

    if (!state.analysis?.ready) {
      setStatus(status, "Capture quality must pass the gate before submission.", "error")
      return
    }

    setStatus(status, modeLabel(prefix, "Submitting request..."), "neutral")

    try {
      const payload = await requestJson(endpoint, {
        method: "POST",
        body: JSON.stringify(bodyBuilder(state.captureData)),
      })
      
      if ((prefix === "login" || prefix === "admin-login" || prefix === "admin-register") && payload.token) {
        localStorage.setItem("si_token", payload.token)
        window.location.href = prefix.startsWith("admin-") ? "/admin" : "/user/dashboard"
        return
      }
      
      renderResultPanel(result, renderResponseCard(payload, prefix))
      renderQuality(prefix, payload.quality)
      setStatus(status, payload.message, "success")
    } catch (error) {
      const quality = error.payload?.quality
      if (quality) {
        renderQuality(prefix, quality)
      }
      const errorId = error.payload?.error_id ? ` (Error ID: ${escapeHtml(error.payload.error_id)})` : ""
      const debugExtra = error.payload?.error_type
        ? ` [${escapeHtml(error.payload.error_type)}: ${escapeHtml(error.payload.error || "")}]`
        : ""

      const verification = error.payload?.verification
      const chainError = error.payload?.blockchain_error
      if (error.payload?.match || verification || chainError) {
        const chips = []
        if (error.payload?.match) {
          chips.push(`<span class="response-chip">Distance ${escapeHtml(error.payload.match.distance)}</span>`)
          chips.push(`<span class="response-chip">Confidence ${escapeHtml(error.payload.match.confidence)}%</span>`)
        }
        if (verification?.state) {
          chips.push(`<span class="response-chip">Verification ${escapeHtml(humanizeState(verification.state))}</span>`)
        }
        if (verification?.resync_attempted) {
          chips.push(`<span class="response-chip">Resync Attempted</span>`)
        }
        if (verification?.tx_hash) {
          chips.push(`<span class="response-chip">Tx ${escapeHtml(String(verification.tx_hash).slice(0, 10))}…</span>`)
        }

        const chainHash = verification?.chain_hash ?? "Not available"
        const localHash = verification?.local_hash ?? "Not available"

        renderResultPanel(
          result,
          `
            <div class="response-grid">
              <strong>${escapeHtml(error.payload?.message || "Request failed.")}${errorId}${debugExtra}</strong>
              ${chips.length ? `<div class="response-chip-row">${chips.join("")}</div>` : ""}
              ${verification ? `
                <div><strong>Local hash</strong><div class="mono">${escapeHtml(localHash)}</div></div>
                <div><strong>Chain hash</strong><div class="mono">${escapeHtml(chainHash)}</div></div>
              ` : ""}
              ${chainError ? `<div><strong>Blockchain error</strong><div>${escapeHtml(chainError)}</div></div>` : ""}
            </div>
          `
        )
      }
      setStatus(status, `${error.payload?.message || "Request failed."}${errorId}${debugExtra}`, "error")
    }
  }

  startButton?.addEventListener("click", handleStartCamera)
  captureButton?.addEventListener("click", handleCapture)
  retakeButton?.addEventListener("click", handleRetake)
  stopButton?.addEventListener("click", handleStop)
  form?.addEventListener("submit", handleSubmit)

  window.addEventListener("beforeunload", () => stopCamera({ silent: true }))
  window.addEventListener("pagehide", () => stopCamera({ silent: true }))
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.stream) {
      state.releasedInBackground = true
      stopCamera({ silent: true })
      return
    }
    if (!document.hidden && state.releasedInBackground) {
      state.releasedInBackground = false
      setBadge(cameraState, "Camera idle", "neutral")
      setStatus(status, "Camera was released while this tab was in the background. Start it again when ready.", "neutral")
    }
  })

  resetCaptureState()
}

function modeLabel(prefix, message) {
  return (prefix === "register" || prefix === "admin-register")
    ? `Enrollment in progress. ${message}`
    : `Authentication in progress. ${message}`
}

function renderInsights(metrics, blockchain) {
  const element = qs("#dashboard-insights")
  if (!element) {
    return
  }

  const insights = []
  if (!blockchain?.ready) {
    insights.push(blockchain?.last_error || "Blockchain is offline, so verification falls back to local records.")
  }
  if (metrics.failed_logins > 0) {
    insights.push(`${metrics.failed_logins} failed login attempt(s) are present in the current audit window.`)
  }
  if (metrics.average_quality < 55 && metrics.total_users > 0) {
    insights.push("Average enrollment quality is below 55. Future registrations should be captured with better lighting.")
  }
  if (metrics.synced_users < metrics.total_users && metrics.total_users > 0) {
    insights.push("Not every identity is chain-synced. Review offline, missing, or mismatch states.")
  }
  if (!insights.length) {
    insights.push("The current system looks stable. No obvious operational anomaly is visible in the latest snapshot.")
  }

  element.innerHTML = insights.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
}

function renderHomeRegistrations(users = [], metrics = {}) {
  const list = qs("#home-registrations")
  if (!list) {
    return
  }

  const countBadge = qs("#home-user-count")
  const total = Number.isFinite(metrics.total_users) ? metrics.total_users : users.length
  const shown = Math.min(users.length, 4)
  const label = total > shown ? `${shown} of ${total}` : `${shown}`
  const identityLabel = shown === 1 ? "identity" : "identities"
  if (countBadge) {
    setBadge(countBadge, `${label} ${identityLabel}`, "neutral")
  }

  if (metrics.error) {
    list.innerHTML = "<li>Unable to load registered identities.</li>"
    return
  }

  if (!users.length) {
    list.innerHTML = "<li>No registered identities yet.</li>"
    return
  }

  list.innerHTML = users
    .slice(0, 4)
    .map((user) => {
      const chainState = user.blockchain_status || "pending"
      const chainLabel = humanizeState(chainState)
      const qualityScore = formatNumber(user.face_quality_score)
      return `
        <li>
          <strong>${escapeHtml(user.name)}</strong>
          <span class="identity-email">${escapeHtml(user.email)}</span>
          <span class="identity-meta">Quality ${escapeHtml(qualityScore)} · ${escapeHtml(chainLabel)}</span>
        </li>
      `
    })
    .join("")
}

function renderUserTable(users = [], metrics = {}) {
  const body = qs("#dashboard-users-body")
  if (!body) {
    return
  }

  const countBadge = qs("#dashboard-user-count")
  const total = Number.isFinite(metrics.total_users) ? metrics.total_users : users.length
  const shown = users.length
  const label = total > shown ? `${shown} of ${total}` : `${shown}`
  const identityLabel = shown === 1 ? "identity" : "identities"
  if (countBadge) {
    setBadge(countBadge, `${label} ${identityLabel}`, "neutral")
  }

  if (metrics.error) {
    body.innerHTML = "<tr><td colspan=\"7\">Unable to load registered identities.</td></tr>"
    return
  }

  if (!users.length) {
    body.innerHTML = "<tr><td colspan=\"7\">No registered identities yet.</td></tr>"
    return
  }

  body.innerHTML = users
    .map((user) => {
      const chainState = user.blockchain_status || "pending"
      const chainTone = toBadgeTone(chainState)
      const chainLabel = humanizeState(chainState)
      const qualityScore = formatNumber(user.face_quality_score)
      return `
        <tr>
          <td>${escapeHtml(user.name)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td>${escapeHtml(formatDate(user.created_at))}</td>
          <td>${escapeHtml(formatDate(user.last_login_at))}</td>
          <td>${escapeHtml(qualityScore)}</td>
          <td><span class="pill ${escapeHtml(chainTone)}">${escapeHtml(chainLabel)}</span></td>
          <td>
            <button type="button" class="btn tertiary delete-user-btn" data-email="${escapeHtml(user.email)}" style="padding: 4px 8px; font-size: 0.8rem; background: transparent; border: 1px solid rgba(255,100,100,0.3); color: #ff6b6b;">Delete</button>
          </td>
        </tr>
      `
    })
    .join("")
}

async function loadOverview() {
  const payload = await requestJson("/overview")
  renderOverviewMetrics(payload.metrics)
  renderChainSummary(payload.blockchain)
  return payload
}

function initHome() {
  loadOverview()
    .then((payload) => {
      renderHomeRegistrations(payload.users || [], payload.metrics || {})
    })
    .catch(() => {
      const chainText = qs("[data-chain-text]")
      if (chainText) {
        chainText.textContent = "Overview unavailable."
      }
      renderHomeRegistrations([], { total_users: 0, error: true })
    })
}

function initRegister() {
  initCaptureWorkflow("register", "/register", (captureData) => ({
    name: qs("#name").value,
    email: qs("#email").value,
    image: captureData,
  }))
}

function initLogin() {
  initCaptureWorkflow("login", "/login", (captureData) => ({
    email: qs("#login-email").value,
    image: captureData,
  }))
}

function initAdminRegister() {
  initCaptureWorkflow("admin-register", "/admin/register", (captureData) => ({
    name: qs("#name").value,
    email: qs("#email").value,
    password: qs("#password").value,
    image: captureData,
  }))
}

function initAdminLogin() {
  initCaptureWorkflow("admin-login", "/admin/login", (captureData) => ({
    email: qs("#admin-login-email").value,
    password: qs("#admin-login-password").value,
    image: captureData,
  }))
}

function initDashboard() {
  const token = localStorage.getItem("si_token")
  if (!token) {
    window.location.href = "/admin/login"
    return
  }

  const decodeJwtPayload = (value) => {
    try {
      const part = value.split(".")[1]
      if (!part) {
        return null
      }
      const normalized = part.replace(/-/g, "+").replace(/_/g, "/")
      const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4)
      const json = atob(padded)
      return JSON.parse(json)
    } catch {
      return null
    }
  }

  const payload = decodeJwtPayload(token)
  if (String(payload?.role || "").toLowerCase() !== "admin") {
    localStorage.removeItem("si_token")
    window.location.href = "/admin/login"
    return
  }

  const refreshButton = qs("#dashboard-refresh")
  const refreshNote = qs("#dashboard-refresh-note")
  let refreshPending = false

  const setRefreshState = (message, tone = "neutral") => {
    if (refreshNote) {
      refreshNote.textContent = message
      refreshNote.className = `refresh-note is-${tone}`
    }
  }

  const setRefreshButtonState = (busy) => {
    if (!refreshButton) {
      return
    }
    refreshButton.disabled = busy
    refreshButton.textContent = busy ? "Refreshing..." : "Refresh data"
  }

  const loadDashboard = async ({ manual = false } = {}) => {
    if (refreshPending) {
      return
    }

    refreshPending = true
    setRefreshButtonState(true)
    if (manual) {
      setRefreshState("Refreshing dashboard data...", "neutral")
    }

    try {
      const payload = await loadOverview()
      renderInsights(payload.metrics, payload.blockchain)
      renderUserTable(payload.users || [], payload.metrics || {})
      setRefreshState(`Last updated ${formatClock()}`, "success")
    } finally {
      refreshPending = false
      setRefreshButtonState(false)
    }
  }

  refreshButton?.addEventListener("click", () => {
    loadDashboard({ manual: true }).catch(() => {
      setRefreshState("Refresh failed. The dashboard data could not be loaded.", "error")
      renderResultPanel(
        qs("#dashboard-insights"),
        "<li>Unable to refresh dashboard data right now.</li>"
      )
    })
  })

  qs("#dashboard-users-body")?.addEventListener("click", async (event) => {
    const btn = event.target.closest(".delete-user-btn");
    if (!btn) return;

    const email = btn.dataset.email;
    if (!email) return;

    if (!confirm(`Are you sure you want to delete identity: ${email}? This action cannot be reversed.`)) {
      return;
    }

    const originalText = btn.textContent;
    btn.textContent = "Deleting...";
    btn.disabled = true;

    try {
      await requestJson(`/users/${encodeURIComponent(email)}`, { method: "DELETE" });
      setRefreshState(`Deleted user ${email} successfully.`, "success");
      loadDashboard({ manual: true }).catch(() => {});
    } catch (error) {
      setRefreshState(`Failed to delete user: ${error.message}`, "error");
      btn.textContent = originalText;
      btn.disabled = false;
    }
  });

  const smtpForm = qs("#smtp-form");
  if (smtpForm) {
    smtpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = smtpForm.querySelector('button[type="submit"]');
      const originalText = btn.textContent;
      
      btn.textContent = "Saving...";
      btn.disabled = true;
      
      try {
        await requestJson("/admin/smtp", {
          method: "POST",
          body: JSON.stringify({
            smtp_email: qs("#smtp-email").value,
            smtp_password: qs("#smtp-password").value
          })
        });
        setRefreshState("SMTP configuration updated dynamically.", "success");
        smtpForm.reset();
      } catch (err) {
        setRefreshState(`SMTP Error: ${err.message}`, "error");
      } finally {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    });
  }

  qs("#clear-logs-btn")?.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all audit logs? This cannot be undone.")) return;
    try {
      await requestJson("/admin/logs", { method: "DELETE" });
      setRefreshState("Audit logs cleared successfully.", "success");
      loadDashboard({ manual: true }).catch(() => {});
    } catch (err) {
      setRefreshState(`Error clearing logs: ${err.message}`, "error");
    }
  });

  qs("#clear-users-btn")?.addEventListener("click", async () => {
    if (!confirm("Are you absolutely sure you want to delete ALL users? This cannot be undone.")) return;
    try {
      await requestJson("/admin/users", { method: "DELETE" });
      setRefreshState("All registered identities cleared.", "success");
      loadDashboard({ manual: true }).catch(() => {});
    } catch (err) {
      setRefreshState(`Error clearing users: ${err.message}`, "error");
    }
  });

  const passwordForm = qs("#admin-password-form");
  if (passwordForm) {
    passwordForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = passwordForm.querySelector('button[type="submit"]');
      const originalText = btn.textContent;
      
      btn.textContent = "Updating...";
      btn.disabled = true;
      
      try {
        await requestJson("/admin/update_password", {
          method: "PUT",
          body: JSON.stringify({
            new_password: qs("#new-admin-password").value
          })
        });
        setRefreshState("Administrator password securely updated.", "success");
        passwordForm.reset();
      } catch (err) {
        setRefreshState(`Error: ${err.message}`, "error");
      } finally {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    });
  }

  const deleteSelfBtn = qs("#delete-self-btn");
  if (deleteSelfBtn) {
    deleteSelfBtn.addEventListener("click", async () => {
      if (!confirm("CRITICAL WARNING: This will permanently delete your Admin biometric identity and access credentials. You will be logged out immediately. Proceed?")) {
        return;
      }
      try {
        await requestJson("/admin/self", { method: "DELETE" });
        localStorage.removeItem("si_token");
        window.location.href = "/";
      } catch (err) {
        setRefreshState(`Failed to revoke access: ${err.message}`, "error");
      }
    });
  }

  loadDashboard().catch(() => {
    setRefreshState("Initial dashboard load failed.", "error")
    renderInsights(
      {
        failed_logins: 0,
        average_quality: 0,
        total_users: 0,
        synced_users: 0,
      },
      { ready: false, last_error: "Dashboard data unavailable." }
    )
    renderUserTable([], { total_users: 0, error: true })
  })

  window.setInterval(() => {
    loadDashboard().catch(() => {})
  }, 30000)
}

function syncScrollEffects() {
  syncHeaderShell()
  syncHomeHero()
}

redirectReloadToHome()
syncScrollEffects()
window.addEventListener("scroll", syncScrollEffects, { passive: true })

if (page === "home") {
  initHome()
}

if (page === "register") {
  initRegister()
}

if (page === "login") {
  initLogin()
}

if (page === "admin") {
  initDashboard()
}

if (page === "admin_register") {
  initAdminRegister()
}

if (page === "admin_login") {
  initAdminLogin()
}

if (page === "profile") {
  initProfile()
}

const signOutBtn = document.getElementById("btn-sign-out")
if (signOutBtn) {
  signOutBtn.addEventListener("click", (e) => {
    e.preventDefault()
    localStorage.removeItem("si_token")
    window.location.href = "/"
  })
}

function initProfile() {
  const token = localStorage.getItem("si_token")
  if (!token) {
    window.location.href = "/login"
    return
  }

  const content = document.getElementById("profile-content")
  const loading = document.getElementById("profile-loading")
  const errorBox = document.getElementById("profile-error")
  const errorMsg = document.getElementById("profile-error-msg")
  const revealToggle = document.getElementById("doc-reveal-toggle")
  const scanOutput = document.getElementById("identity-scan-output")
  const scanStatus = document.getElementById("scan-status")
  const scanMatch = document.getElementById("scan-match")
  const scanLinked = document.getElementById("scan-linked")
  const scanLinkedIds = document.getElementById("identity-scan-linked-ids")
  const scanMessage = document.getElementById("identity-scan-message")
  const docsEmpty = document.getElementById("identity-documents-empty")
  const docsList = document.getElementById("identity-documents-list")
  const uploadForm = document.getElementById("identity-doc-upload-form")
  const uploadStatus = document.getElementById("identity-doc-status")
  const docCode = document.getElementById("doc-code")
  const docLabelField = document.getElementById("doc-label-field")
  const docLabel = document.getElementById("doc-label")
  const docNumber = document.getElementById("doc-number")
  const docFile = document.getElementById("doc-file")
  const docPreview = document.getElementById("identity-doc-preview")
  const docPreviewMedia = document.getElementById("identity-doc-preview-media")
  const docPreviewTitle = document.getElementById("identity-doc-preview-title")
  const docPreviewNumber = document.getElementById("identity-doc-preview-number")
  const docPreviewMeta = document.getElementById("identity-doc-preview-meta")

  const revealKey = "si_reveal_docs"
  const getRevealState = () => localStorage.getItem(revealKey) === "1"
  const setRevealState = (value) => localStorage.setItem(revealKey, value ? "1" : "0")

  if (revealToggle) {
    revealToggle.checked = getRevealState()
  }

  function showDocLabelIfNeeded() {
    if (!docCode || !docLabelField) {
      return
    }
    const isOther = docCode.value === "other"
    docLabelField.style.display = isOther ? "block" : "none"
    if (!isOther && docLabel) {
      docLabel.value = ""
    }
    updatePreview()
  }

  let previewObjectUrl = null

  function formatBytes(bytes) {
    const value = Number(bytes)
    if (!Number.isFinite(value) || value <= 0) {
      return "0 B"
    }
    const units = ["B", "KB", "MB", "GB"]
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
    const scaled = value / (1024 ** index)
    return `${scaled.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
  }

  function maskPreviewNumber(docCodeValue, rawValue) {
    const value = String(rawValue || "").trim()
    if (!value) {
      return "--"
    }
    const digitsOnly = value.replace(/\D/g, "")
    if (docCodeValue === "aadhaar" && /^\d{12}$/.test(digitsOnly)) {
      return `XXXX-XXXX-${digitsOnly.slice(-4)}`
    }
    const last4 = value.slice(-4)
    const maskedLength = Math.max(0, value.length - 4)
    const masked = `${"*".repeat(maskedLength)}${last4}`
    return maskedLength ? masked : `****${last4}`
  }

  function getSelectedDocName() {
    const selected = docCode?.value || ""
    if (selected === "other") {
      return docLabel?.value?.trim() ? docLabel.value.trim() : "Other Document"
    }
    const optionText = docCode?.selectedOptions?.[0]?.textContent
    return optionText || humanizeState(selected) || "Document"
  }

  function clearPreview() {
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl)
      previewObjectUrl = null
    }
    if (docPreviewMedia) {
      docPreviewMedia.innerHTML = ""
    }
    if (docPreviewTitle) {
      docPreviewTitle.textContent = "Document preview"
    }
    if (docPreviewNumber) {
      docPreviewNumber.textContent = "--"
      delete docPreviewNumber.dataset.full
      delete docPreviewNumber.dataset.masked
    }
    if (docPreviewMeta) {
      docPreviewMeta.textContent = "Select a file to preview."
    }
    if (docPreview) {
      docPreview.style.display = "none"
    }
  }

  function updatePreview() {
    const file = docFile?.files?.[0]
    if (!docPreview || !docPreviewMedia || !docPreviewTitle || !docPreviewNumber || !docPreviewMeta) {
      return
    }
    if (!file) {
      clearPreview()
      return
    }

    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl)
      previewObjectUrl = null
    }

    const docName = getSelectedDocName()
    docPreviewTitle.textContent = `${docName} • File preview`

    const fullNumber = String(docNumber?.value || "").trim()
    docPreviewNumber.dataset.full = fullNumber
    docPreviewNumber.dataset.masked = maskPreviewNumber(docCode?.value || "", fullNumber)
    docPreviewNumber.textContent = docPreviewNumber.dataset.masked

    const fileType = file.type || (file.name?.toLowerCase().endsWith(".pdf") ? "application/pdf" : "document")
    const fileTypeLabel = fileType === "application/pdf" ? "PDF" : fileType.startsWith("image/") ? "Image" : fileType
    docPreviewMeta.textContent = `${fileTypeLabel} • ${formatBytes(file.size)} • Hover to reveal number`

    docPreview.style.display = "flex"

    if (fileType.startsWith("image/")) {
      const reader = new FileReader()
      reader.onload = () => {
        const src = reader.result
        docPreviewMedia.innerHTML = `<img src="${escapeHtml(String(src || ""))}" alt="Selected document preview" />`
      }
      reader.onerror = () => {
        docPreviewMedia.innerHTML = `<div class="si-doc-preview-pdf">IMAGE</div>`
      }
      reader.readAsDataURL(file)
      return
    }

    if (fileType === "application/pdf") {
      previewObjectUrl = URL.createObjectURL(file)
      docPreviewMedia.innerHTML = `<embed src="${escapeHtml(previewObjectUrl)}" type="application/pdf" />`
      return
    }

    docPreviewMedia.innerHTML = `<div class="si-doc-preview-pdf">FILE</div>`
  }

  if (docPreviewNumber) {
    docPreviewNumber.addEventListener("mouseenter", () => {
      if (docPreviewNumber.dataset.full) {
        docPreviewNumber.textContent = docPreviewNumber.dataset.full
      }
    })
    docPreviewNumber.addEventListener("mouseleave", () => {
      if (docPreviewNumber.dataset.masked) {
        docPreviewNumber.textContent = docPreviewNumber.dataset.masked
      }
    })
  }

  docFile?.addEventListener("change", updatePreview)
  docNumber?.addEventListener("input", updatePreview)
  docCode?.addEventListener("change", updatePreview)
  docLabel?.addEventListener("input", updatePreview)

  function renderScan(payload, reveal) {
    const docs = Array.isArray(payload?.documents) ? payload.documents : []
    const hasDocs = docs.length > 0

    if (scanStatus) {
      scanStatus.innerHTML = `<span class="badge success">Face Verified</span>`
    }
    if (scanMatch) {
      scanMatch.innerHTML = `<span class="badge success">Found in Database</span>`
    }
    if (scanLinked) {
      scanLinked.innerHTML = hasDocs ? `<span class="badge neutral">${docs.length} linked</span>` : `<span class="badge warning">None</span>`
    }

    if (scanLinkedIds) {
      if (!hasDocs) {
        scanLinkedIds.innerHTML = ""
      } else {
        scanLinkedIds.innerHTML = docs
          .map((doc) => {
            const label = doc.display_label || doc.doc_label || doc.doc_code || "Document"
            const number = reveal && doc.doc_number_full ? doc.doc_number_full : doc.doc_number_masked
            return `<li><span class="si-scan-id-label">${escapeHtml(label)}</span><span class="si-scan-id-number">${escapeHtml(number || "--")}</span></li>`
          })
          .join("")
      }
    }

    if (scanMessage) {
      const standard = ["aadhaar", "pan", "driving_license", "passport", "voter_id"]
      const present = new Set(docs.map((doc) => String(doc.doc_code || "").toLowerCase()))
      const missingStandard = standard.some((code) => !present.has(code))

      const notes = []
      if (!hasDocs) {
        notes.push("No identity records found for this individual.")
      } else if (missingStandard) {
        notes.push("Some identity records were found. Additional documents can be uploaded.")
      }
      notes.push("Users can upload additional identity documents to enhance verification.")
      scanMessage.textContent = notes.join(" ")
    }
  }

  function renderDocuments(documents, reveal) {
    if (!docsList || !docsEmpty) {
      return
    }
    const docs = Array.isArray(documents) ? documents : []
    if (!docs.length) {
      docsEmpty.textContent = "No linked identity documents yet."
      docsEmpty.style.display = "block"
      docsList.innerHTML = ""
      return
    }

    docsEmpty.style.display = "none"
    docsList.innerHTML = docs
      .map((doc) => {
        const id = doc.id
        const label = doc.display_label || doc.doc_label || doc.doc_code || "Document"
        const number = reveal && doc.doc_number_full ? doc.doc_number_full : doc.doc_number_masked
        const hasFile = Boolean(doc.has_file)
        const download = hasFile && doc.download_url
          ? `<button type="button" class="btn tertiary doc-download-btn" data-download-url="${escapeHtml(doc.download_url)}" data-filename="${escapeHtml(doc.original_filename || "document")}" style="padding: 4px 8px; font-size: 0.85rem;">Download</button>`
          : ""
        return `
          <li style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.6rem 0.75rem; border: 1px solid var(--border); border-radius: 10px; background: var(--bg-app);">
            <div style="min-width: 0;">
              <strong style="color: var(--text-primary);">${escapeHtml(label)}</strong>
              <div style="color: var(--text-tertiary); font-size: 0.9rem; margin-top: 0.15rem; word-break: break-word;">${escapeHtml(number || "--")}</div>
            </div>
            <div style="display: flex; gap: 0.5rem; flex-shrink: 0;">
              ${download}
              <button type="button" class="btn tertiary doc-delete-btn" data-doc-id="${escapeHtml(id)}" style="padding: 4px 8px; font-size: 0.85rem; background: transparent; border: 1px solid rgba(255,100,100,0.3); color: #ff6b6b;">Delete</button>
            </div>
          </li>
        `
      })
      .join("")
  }

  async function loadScanAndDocs() {
    const reveal = getRevealState()
    if (scanOutput) {
      scanOutput.textContent = "Loading scan..."
    }
    if (scanStatus) {
      scanStatus.innerHTML = `<span class="badge neutral">Loading</span>`
    }
    if (scanMatch) {
      scanMatch.innerHTML = `<span class="badge neutral">--</span>`
    }
    if (scanLinked) {
      scanLinked.innerHTML = `<span class="badge neutral">--</span>`
    }
    if (scanLinkedIds) {
      scanLinkedIds.innerHTML = ""
    }
    if (scanMessage) {
      scanMessage.textContent = ""
    }
    try {
      const payload = await requestJson(`/identity-scan?reveal=${reveal ? 1 : 0}`, { method: "GET" })
      if (scanOutput) {
        scanOutput.textContent = payload.report_text || "Scan unavailable."
      }
      renderScan(payload, reveal)
      renderDocuments(payload.documents || [], reveal)
    } catch (err) {
      if (scanOutput) {
        scanOutput.textContent = err.payload?.message || err.message || "Failed to load scan."
      }
      if (scanStatus) {
        scanStatus.innerHTML = `<span class="badge error">Unavailable</span>`
      }
      if (scanMatch) {
        scanMatch.innerHTML = `<span class="badge error">Error</span>`
      }
      if (scanLinked) {
        scanLinked.innerHTML = `<span class="badge error">--</span>`
      }
      if (scanMessage) {
        scanMessage.textContent = err.payload?.message || err.message || "Failed to load scan."
      }
      renderDocuments([], false)
    }
  }

  requestJson("/profile", { method: "GET" })
    .then((payload) => {
      const user = payload.user
      document.getElementById("profile-name").textContent = user.name
      document.getElementById("profile-email").textContent = user.email
      document.getElementById("profile-hash").textContent = user.identity_hash || "..."

      const chainStatus = payload.blockchain_state || user.blockchain_status || "Not Connected"
      const chainBadge = document.getElementById("profile-chain-status")
      chainBadge.textContent = humanizeState(chainStatus)
      chainBadge.className = `badge ${toBadgeTone(chainStatus)}`
      const chainDetail = document.getElementById("profile-chain-detail")
      const chainInfo = payload.blockchain || {}
      const contractAddress = chainInfo.contract_address || "Not configured"
      const rpcUrl = chainInfo.rpc_url || "--"
      const deployed = Boolean(chainInfo.deployed)
      const lastError = payload.blockchain_error || chainInfo.last_error

      chainBadge.title = lastError
        ? `${lastError}`
        : `RPC: ${rpcUrl}\nContract: ${contractAddress}\nDeployed: ${deployed ? "Yes" : "No"}`

      if (chainDetail) {
        if (String(chainStatus).toLowerCase() === "active") {
          chainDetail.textContent = `RPC connected • Contract deployed`
        } else {
          chainDetail.textContent = lastError
            ? `${lastError}`
            : `RPC: ${rpcUrl} • Contract: ${contractAddress}`
        }
      }

      document.getElementById("profile-quality").textContent = user.face_quality_score

      loading.style.display = "none"
      content.style.display = "block"

      showDocLabelIfNeeded()
      docCode?.addEventListener("change", showDocLabelIfNeeded)

      revealToggle?.addEventListener("change", () => {
        setRevealState(Boolean(revealToggle.checked))
        loadScanAndDocs().catch(() => {})
      })

      docsList?.addEventListener("click", async (event) => {
        const downloadBtn = event.target.closest(".doc-download-btn")
        if (downloadBtn) {
          const rawUrl = downloadBtn.dataset.downloadUrl || ""
          const fallbackName = downloadBtn.dataset.filename || "document"
          const path = rawUrl.startsWith(API_BASE) ? rawUrl.slice(API_BASE.length) : rawUrl
          try {
            setStatus(uploadStatus, "Preparing download...", "neutral")
            const { blob, disposition } = await requestBlob(path, { method: "GET" })
            const match = /filename\\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?/i.exec(disposition || "")
            const encodedName = match?.[1] || match?.[2] || ""
            const filename = encodedName ? decodeURIComponent(encodedName) : fallbackName

            const objectUrl = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = objectUrl
            a.download = filename
            document.body.appendChild(a)
            a.click()
            a.remove()
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 5000)
            setStatus(uploadStatus, "Download started.", "success")
          } catch (err) {
            setStatus(uploadStatus, err.payload?.message || err.message || "Download failed.", "error")
          }
          return
        }

        const deleteBtn = event.target.closest(".doc-delete-btn")
        if (!deleteBtn) {
          return
        }
        const docId = deleteBtn.dataset.docId
        if (!docId) {
          return
        }
        if (!confirm("Delete this linked identity document?")) {
          return
        }
        try {
          setStatus(uploadStatus, "Deleting document...", "neutral")
          await requestJson(`/identity-documents/${encodeURIComponent(docId)}`, { method: "DELETE" })
          setStatus(uploadStatus, "Document deleted.", "success")
          await loadScanAndDocs()
        } catch (err) {
          setStatus(uploadStatus, err.payload?.message || err.message || "Delete failed.", "error")
        }
      })

      uploadForm?.addEventListener("submit", async (event) => {
        event.preventDefault()
        try {
          const selectedFile = docFile?.files?.[0]
          if (!selectedFile) {
            setStatus(uploadStatus, "Select a document file to upload.", "error")
            docFile?.focus?.()
            return
          }

          const formData = new FormData()
          const selectedCode = docCode?.value
          formData.append("doc_code", selectedCode || "")
          if (selectedCode === "other") {
            formData.append("doc_label", docLabel?.value || "")
          }
          formData.append("doc_number", docNumber?.value || "")
          formData.append("file", selectedFile)

          setStatus(uploadStatus, "Uploading document...", "neutral")
          await requestFormData("/identity-documents", formData, { method: "POST" })
          setStatus(uploadStatus, "Document stored.", "success")
          if (docFile) {
            docFile.value = ""
          }
          clearPreview()
          await loadScanAndDocs()
        } catch (err) {
          setStatus(uploadStatus, err.payload?.message || err.message || "Upload failed.", "error")
        }
      })

      loadScanAndDocs().catch(() => {})
    })
    .catch((err) => {
      loading.style.display = "none"
      errorMsg.textContent = err.message
      errorBox.style.display = "block"
      localStorage.removeItem("si_token")
    })
}
