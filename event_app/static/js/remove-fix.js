// Fix for form submission in Vercel environment
document.addEventListener('DOMContentLoaded', function() {
    // Find all remove buttons and attach direct click handlers
    document.querySelectorAll('.remove-participant-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            const userName = this.getAttribute('data-user-name') || 'this participant';
            
            if (confirm(`Are you sure you want to remove ${userName}?`)) {
                // First try the direct API endpoint
                fetch(`/api/remove-user/${userId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Reload the page to show updated data, preserve tab if provided
                        const tab = btn.getAttribute('data-tab');
                        if (tab) {
                          const url = new URL(window.location.href);
                          url.searchParams.set('tab', tab);
                          window.location.href = url.toString();
                        } else {
                          window.location.reload();
                        }
                    } else {
                        alert('Error removing user: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Fallback to traditional form submission if API fails
                    console.error('API Error:', error);
                    const form = document.createElement('form');
                    form.method = 'POST';
                    const tab = btn.getAttribute('data-tab');
                    form.action = `/admin/user/remove/${userId}` + (tab ? `?tab=${encodeURIComponent(tab)}` : '');
                    document.body.appendChild(form);
                    form.submit();
                });
            }
        });
    });
    
    // Handle complete removal buttons (removes from both users and allowed_users tables)
    document.querySelectorAll('.complete-remove-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            const userName = this.getAttribute('data-user-name') || 'this participant';
            const phone = this.getAttribute('data-phone') || '';
            
            if (confirm(`Are you sure you want to COMPLETELY REMOVE ${userName} (${phone})?\n\nThis will remove their credentials from the database and they won't be able to login again.`)) {
                console.log(`Attempting to remove user with ID: ${userId}`);
                
                // Always use the Vercel-style API URL to ensure consistency
                const apiUrl = `/api/complete-remove-user/${userId}`;
                
                console.log(`Removing user with ID ${userId} using API URL: ${apiUrl}`);
                
                // Use the complete remove API endpoint
                fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    console.log(`Response status: ${response.status}`);
                    return response.json().catch(e => {
                        // Handle case where response isn't valid JSON
                        return { 
                            success: false, 
                            error: `Server returned ${response.status}` 
                        };
                    });
                })
                .then(data => {
                    console.log('Response data:', data);
                    if (data.success) {
                        alert(`User ${userName} has been completely removed.`);
                        // Reload the page to show updated data
                        window.location.reload();
                    } else {
                        alert('Error removing user: ' + (data.error || data.message || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('API Error:', error);
                    alert(`Network error: ${error.message}. Please try again later.`);
                });
            }
        });
    });
});
