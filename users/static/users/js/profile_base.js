document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('construction-modal');
    const backdrop = document.getElementById('construction-backdrop');
    const closeBtn = document.getElementById('construction-close');
    const unfinishedLinks = document.querySelectorAll('.unfinished-link');

    function openModal(e) {
        e.preventDefault();
        if (!modal || !backdrop) return;
        backdrop.classList.add('show');
        modal.classList.add('show');
    }

    function closeModal() {
        if (!modal || !backdrop) return;
        backdrop.classList.remove('show');
        modal.classList.remove('show');
    }

    unfinishedLinks.forEach(link => {
        link.addEventListener('click', openModal);
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    if (backdrop) {
        backdrop.addEventListener('click', closeModal);
    }

    const searchInput = document.getElementById('sidebar-search');
    const links = document.querySelectorAll('.sidebar-link');

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase().trim();

            links.forEach(link => {
                const text = link.textContent.toLowerCase();
                link.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }
});