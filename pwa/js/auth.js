// -------------------------------
// auth.js
// Handles OTP request, verification & login
// -------------------------------

const API_BASE = "http://${window.location.hostname}:8000/api"; // Django API

// -------------------------------
// Request OTP
// -------------------------------
async function requestOTP(phone) {
    try {
        const res = await fetch(`${API_BASE}/request-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone })
        });

        const data = await res.json();
        if (data.ok) {
            console.log("OTP sent successfully:", data);
            return { success: true, message: "OTP sent" };
        } else {
            console.error("Request OTP failed:", data.error);
            return { success: false, message: data.error };
        }
    } catch (err) {
        console.error("Network error:", err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Verify OTP
// -------------------------------
async function verifyOTP(phone, otp) {
    try {
        const res = await fetch(`${API_BASE}/verify-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, otp })
        });

        const data = await res.json();
        if (data.ok) {
            console.log("OTP verified successfully:", data.user);
            // Store user info in localStorage or session
            localStorage.setItem("user", JSON.stringify(data.user));
            return { success: true, user: data.user };
        } else {
            console.error("OTP verification failed:", data.error);
            return { success: false, message: data.error };
        }
    } catch (err) {
        console.error("Network error:", err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Admin login (phone + password)
// -------------------------------
async function adminLogin(phone, password) {
    try {
        const res = await fetch(`${API_BASE}/admin-login/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, password })
        });

        const data = await res.json();
        if (data.ok) {
            console.log("Admin login successful:", data.user);
            localStorage.setItem("admin", JSON.stringify(data.user));
            return { success: true, user: data.user };
        } else {
            console.error("Admin login failed:", data.error);
            return { success: false, message: data.error };
        }
    } catch (err) {
        console.error("Network error:", err);
        return { success: false, message: "Network error" };
    }
}

// -------------------------------
// Example usage
// -------------------------------

// Request OTP
// requestOTP("255769922257");

// Verify OTP
// verifyOTP("255769922257", "1234");

// Admin login
// adminLogin("255769922257", "yourpassword");
