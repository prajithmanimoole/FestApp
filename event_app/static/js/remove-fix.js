// Fix for form submission in Vercel environment
document.addEventListener('DOMContentLoaded', function() {
    // Find all remove buttons and attach direct click handlers
    document.querySelectorAll('.remove-participant-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            const userName = this.getAttribute('data-user-name') || 'this participant';
            
            if (confirm(`Are you sure you want to remove ${userName}?`)) {
                // First try the direct API endpoint that works on Vercel
                fetch(`/api/remove-user/${userId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Reload the page to show updated data
                        window.location.reload();
                    } else {
                        alert('Error removing user: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Fallback to traditional form submission if API fails
                    console.error('API Error:', error);
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = `/admin/user/remove/${userId}`;
                    document.body.appendChild(form);
                    form.submit();
                });
            }
        });
    });
});
