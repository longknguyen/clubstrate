const revealBtn = document.getElementById('reveal-email');
const emailText = document.getElementById('email-text');
const openPasswordModalBtn = document.getElementById('open-password-modal');
const passwordBackdrop = document.getElementById('password-backdrop');
const passwordModal = document.getElementById('password-modal');
const passwordCloseBtn = document.getElementById('password-close');
const passwordCancelBtn = document.getElementById('password-cancel');
const passwordForm = document.getElementById('password-form');
const passwordDoneBtn = document.getElementById('password-done');
const passwordErrorBanner = document.getElementById('password-error-banner');

let revealed = false;

if (revealBtn && emailText) {
    revealBtn.addEventListener('click', () => {
        revealed = !revealed;
        emailText.textContent = revealed ? emailText.dataset.real : emailText.dataset.masked;
        revealBtn.textContent = revealed ? 'Hide' : 'Reveal';
    });
}

function openPasswordModal() {
    if (!passwordBackdrop || !passwordModal) return;
    passwordBackdrop.classList.add('show');
    passwordModal.classList.add('show');
    passwordModal.setAttribute('aria-hidden', 'false');
    window.setTimeout(() => {
        const firstInput = passwordModal.querySelector('input');
        if (firstInput) firstInput.focus();
    }, 20);
}

function closePasswordModal() {
    if (!passwordBackdrop || !passwordModal) return;
    passwordBackdrop.classList.remove('show');
    passwordModal.classList.remove('show', 'is-success');
    passwordModal.setAttribute('aria-hidden', 'true');
    clearPasswordErrors();
    if (passwordForm) {
        passwordForm.reset();
    }
}

function clearPasswordErrors() {
    if (passwordErrorBanner) {
        passwordErrorBanner.textContent = '';
        passwordErrorBanner.classList.add('joined-cio-hidden');
        passwordErrorBanner.classList.remove('is-success');
    }
    document.querySelectorAll('[data-password-error-for]').forEach((errorEl) => {
        errorEl.textContent = '';
        errorEl.classList.add('joined-cio-hidden');
    });
}

function showPasswordErrors(payload) {
    clearPasswordErrors();
    if (passwordErrorBanner && payload.non_field_errors && payload.non_field_errors.length) {
        passwordErrorBanner.textContent = payload.non_field_errors.join(' ');
        passwordErrorBanner.classList.remove('joined-cio-hidden');
    }
    if (payload.errors) {
        Object.entries(payload.errors).forEach(([fieldName, entries]) => {
            const errorEl = document.querySelector(`[data-password-error-for="${fieldName}"]`);
            if (!errorEl) return;
            errorEl.textContent = entries.map((entry) => entry.message).join(' ');
            errorEl.classList.remove('joined-cio-hidden');
        });
    }
}

if (openPasswordModalBtn) {
    openPasswordModalBtn.addEventListener('click', openPasswordModal);
}

if (passwordCloseBtn) {
    passwordCloseBtn.addEventListener('click', closePasswordModal);
}

if (passwordCancelBtn) {
    passwordCancelBtn.addEventListener('click', closePasswordModal);
}

if (passwordBackdrop) {
    passwordBackdrop.addEventListener('click', closePasswordModal);
}

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && passwordModal && passwordModal.classList.contains('show')) {
        closePasswordModal();
    }
});

if (passwordForm) {
    passwordForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearPasswordErrors();

        if (passwordDoneBtn) {
            passwordDoneBtn.disabled = true;
        }

        const response = await fetch(passwordForm.action, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new FormData(passwordForm),
            credentials: 'same-origin',
        });

        const payload = await response.json();

        if (!response.ok || !payload.ok) {
            showPasswordErrors(payload);
            if (passwordDoneBtn) {
                passwordDoneBtn.disabled = false;
            }
            return;
        }

        if (passwordErrorBanner) {
            passwordErrorBanner.textContent = payload.message || 'Password changed successfully.';
            passwordErrorBanner.classList.remove('joined-cio-hidden');
            passwordErrorBanner.classList.add('is-success');
        }

        if (passwordModal) {
            passwordModal.classList.add('is-success');
        }

        if (typeof window.launchSuccessConfetti === 'function') {
            window.launchSuccessConfetti({fullScreen: true});
        }

        window.setTimeout(() => {
            if (passwordDoneBtn) {
                passwordDoneBtn.disabled = false;
            }
            closePasswordModal();
        }, 1000);
    });
}
