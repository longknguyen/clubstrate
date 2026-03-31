document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('construction-modal');
    const backdrop = document.getElementById('construction-backdrop');
    const closeBtn = document.getElementById('construction-close');

    const unfinishedLinks = document.querySelectorAll('.unfinished-link');

    function openModal(e) {
        e.preventDefault();
        modal.style.display = 'block';
        backdrop.style.display = 'block';
    }

    function closeModal() {
        modal.style.display = 'none';
        backdrop.style.display = 'none';
    }

    unfinishedLinks.forEach(link => {
        link.addEventListener('click', openModal);
    });

    closeBtn.addEventListener('click', closeModal);
    backdrop.addEventListener('click', closeModal);
});

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('sidebar-search');
    const links = document.querySelectorAll('.sidebar-link');

    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.toLowerCase().trim();

        links.forEach(link => {
            const text = link.textContent.toLowerCase();
            link.style.display = text.includes(query) ? '' : 'none';
        });
    });
});