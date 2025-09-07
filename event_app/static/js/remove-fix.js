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
    
    // Handle complete removal buttons (removes from both users and allowed_users tables)
    document.querySelectorAll('.complete-remove-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            const userName = this.getAttribute('data-user-name') || 'this participant';
            const phone = this.getAttribute('data-phone') || '';
            
            if (confirm(`Are you sure you want to COMPLETELY REMOVE ${userName} (${phone})?\n\nThis will remove their credentials from the database and they won't be able to login again.`)) {
                console.log(`Attempting to remove user with ID: ${userId}`);
                
                // Determine if we're running locally or on Vercel
                const isLocal = window.location.hostname === '127.0.0.1' || 
                               window.location.hostname === 'localhost';
                
                // Use different URL format based on environment
                const apiUrl = isLocal 
                    ? `/admin/api-complete-remove-user/${userId}` 
                    : `/api/complete-remove-user/${userId}`;
                
                console.log(`Using API URL: ${apiUrl}`);
                
                // Use the complete remove API endpoint
                fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    console.log(`Response status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Server returned ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Response data:', data);
                    if (data.success) {
                        // Reload the page to show updated data
                        window.location.reload();
                    } else {
                        alert('Error completely removing user: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('API Error:', error);
                    alert(`Failed to remove user: ${error.message}. Please check console for details.`);
                });
            }
        });
    });
});
