document.addEventListener('contextmenu', function(e) {
    if (e.target.closest('.item')) {
        e.preventDefault();
        const item = e.target.closest('.item');
        const itemId = item.dataset.id;
        const itemName = e.target.closest('.item').querySelector('div').textContent.split(' (')[0];
        const contextMenu = document.getElementById('context-menu');
        
        contextMenu.style.top = `${e.pageY}px`;
        contextMenu.style.left = `${e.pageX}px`;
        contextMenu.classList.remove('hidden');

        document.querySelectorAll('.context-item').forEach(menuItem => {
            menuItem.addEventListener('click', async function() {
                const action = this.dataset.action;
                if (action === 'download') {
                    window.location.href = `/files/api/download/${itemId}/`;
                } else if (action === 'delete') {
                    if (confirm('آیا مطمئن هستید که می‌خواهید این مورد را حذف کنید؟')) {
                        await fetch(`/files/api/delete/${itemId}/`, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': getCookie('csrftoken')
                            }
                        });
                        loadItems(window.currentParentId); // استفاده از currentParentId
                    }
                } else if (action === 'rename') {
                    openRenameModal(itemId, itemName);
                }
                contextMenu.classList.add('hidden');
            });
        });
    }
});

document.addEventListener('click', function() {
    document.getElementById('context-menu').classList.add('hidden');
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}