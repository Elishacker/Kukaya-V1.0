// -------------------------------
// auth.js
// Handles OTP request, verification & login
// -------------------------------

const API_BASE = `http://${window.location.hostname}:8000/api`;

// -------------------------------
// Helper: GET CSRF token from cookie
// -------------------------------
function getCookie(name) {
    const cookieValue = document.cookie.split("; ").find(row => row.startsWith(name + "="));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : null;
}

const csrftoken = getCookie("csrftoken");

// -------------------------------
// API Fetch wrapper (with credentials & CSRF)
// -------------------------------
async function apiFetch(path, opts = {}) {
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const headers = new Headers(opts.headers || {});
    headers.set("Accept", "application/json");
    if (opts.body && !(opts.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (csrftoken) headers.set("X-CSRFToken", csrftoken);

    const res = await fetch(url, { ...opts, headers, credentials: "include" });

    if (res.status === 401) {
        alert("Session expired or not authenticated. Please login.");
        window.location.href = "../index.html";
        return null;
    }

    const text = await res.text();
    try {
        return JSON.parse(text || "{}");
    } catch {
        return { ok: false, error: "Invalid JSON response", raw: text };
    }
}

// -------------------------------
// Request OTP
// -------------------------------
async function requestOTP(phone) {
    try {
        const data = await apiFetch("/request-otp/", {
            method: "POST",
            body: JSON.stringify({ phone }),
        });
        if (data.ok) return { success: true, message: "OTP sent" };
        return { success: false, message: data.error || "Failed to send OTP" };
    } catch (err) {
        console.error(err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Verify OTP
// -------------------------------
async function verifyOTP(phone, otp) {
    try {
        const data = await apiFetch("/verify-otp/", {
            method: "POST",
            body: JSON.stringify({ phone, otp }),
        });
        if (data && data.ok && data.user) {
            // Always fetch profile from server session to confirm current user
            await getCurrentUser();
            return { success: true, user: data.user };
        }
        return { success: false, message: data.error || "OTP verification failed" };
    } catch (err) {
        console.error(err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Admin login (phone + password)
// -------------------------------
async function adminLogin(phone, password) {
    try {
        const data = await apiFetch("/admin-login/", {
            method: "POST",
            body: JSON.stringify({ phone, password }),
        });
        if (data && data.ok && data.user) {
            await getCurrentUser();
            return { success: true, user: data.user };
        }
        return { success: false, message: data.error || "Admin login failed" };
    } catch (err) {
        console.error(err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Get current logged-in user from server session
// -------------------------------
let currentUser = null;

async function getCurrentUser() {
    try {
        const data = await apiFetch("/auth/profile", { method: "GET" });
        if (data && data.ok && data.user) {
            currentUser = data.user;
            document.getElementById("account-phone").textContent = currentUser.phone || "N/A";
            document.getElementById("account-role").textContent = currentUser.role || "User";
            return currentUser;
        } else {
            currentUser = null;
            window.location.href = "../index.html";
            return null;
        }
    } catch (err) {
        console.error(err);
        currentUser = null;
        window.location.href = "../index.html";
        return null;
    }
}

// -------------------------------
// Logout
// -------------------------------
async function logout() {
    try {
        await apiFetch("/auth/logout/", { method: "POST" });
    } catch (err) {
        console.error(err);
    } finally {
        currentUser = null;
        window.location.href = "../index.html";
    }
}
