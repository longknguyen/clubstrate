const revealBtn = document.getElementById('reveal-email');
const emailText = document.getElementById('email-text');

let revealed = false;

revealBtn.addEventListener('click', () => {
    revealed = !revealed;
    emailText.textContent = revealed ? emailText.dataset.real : emailText.dataset.masked;
    revealBtn.textContent = revealed ? 'Hide' : 'Reveal';
});