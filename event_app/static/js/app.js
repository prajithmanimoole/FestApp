// Game filter functionality
(function(){
  const filterInput = document.getElementById('gameFilter');
  if (!filterInput) return;
  filterInput.addEventListener('input', function(){
    const q = (this.value || '').toLowerCase();
    document.querySelectorAll('.game-card').forEach(function(item){
      const name = (item.getAttribute('data-game-name') || '').toLowerCase();
      item.style.display = name.indexOf(q) !== -1 ? '' : 'none';
    });
  });
})();

// Click-to-remove functionality for participants
(function(){
  // Handle participant removal
  function handleParticipantRemoval(event) {
    const participantRow = event.target.closest('tr[data-participant-id]');
    if (!participantRow) return;
    
    // Don't trigger on form elements or buttons (unless it's a remove button)
    const isRemoveButton = event.target.closest('.remove-participant-btn, .complete-remove-btn');
    if (!isRemoveButton && event.target.closest('form, button, input, select, textarea, a')) return;
    
    const participantId = participantRow.getAttribute('data-participant-id');
    const participantName = participantRow.getAttribute('data-participant-name');
    const participantPhone = participantRow.getAttribute('data-participant-phone');
    
    if (participantId && participantName) {
      // Get current active tab to preserve it after removal
      const activeTab = document.querySelector('.nav-link.active')?.getAttribute('aria-controls') || 'overview';
      
      if (confirm(`Click to remove: Are you sure you want to remove ${participantName}?`)) {
        // Check if this is in the overview section (complete removal) or games section (partial removal)
        const isOverviewSection = participantRow.closest('#overview') !== null;
        
        if (isOverviewSection) {
          // Complete removal for overview section
          fetch(`/admin/api-complete-remove-user/${participantId}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            }
          }).then(response => {
            if (response.ok) {
              // Redirect with tab parameter to preserve current tab
              window.location.href = `/admin?tab=${activeTab}`;
            } else {
              return response.json().then(data => {
                throw new Error(data.error || 'Failed to remove participant');
              });
            }
          }).catch(error => {
            console.error('Error:', error);
            alert(`Error removing participant: ${error.message}. Please try again.`);
          });
        } else {
          // Partial removal for games section - find and submit the remove form
          const removeForm = document.querySelector(`form[action*="/admin/user/remove/${participantId}"]`);
          
          if (removeForm) {
            // Add tab parameter to form action to preserve current tab
            const formAction = removeForm.getAttribute('action');
            const separator = formAction.includes('?') ? '&' : '?';
            removeForm.setAttribute('action', `${formAction}${separator}tab=${activeTab}`);
            removeForm.submit();
          } else {
            // Fallback to partial removal API
            fetch(`/api/remove-user/${participantId}`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              }
            }).then(response => {
              if (response.ok) {
                window.location.href = `/admin?tab=${activeTab}`;
              } else {
                return response.json().then(data => {
                  throw new Error(data.error || 'Failed to remove participant');
                });
              }
            }).catch(error => {
              console.error('Error:', error);
              alert(`Error removing participant: ${error.message}. Please try again.`);
            });
          }
        }
      }
    }
  }
  
  // Handle button click events specifically
  function handleButtonClick(event) {
    const button = event.target.closest('.remove-participant-btn, .complete-remove-btn');
    if (!button) return;
    
    event.preventDefault();
    event.stopPropagation();
    
    const userId = button.getAttribute('data-user-id');
    const userName = button.getAttribute('data-user-name');
    const userPhone = button.getAttribute('data-phone');
    const currentTab = button.getAttribute('data-tab') || document.querySelector('.nav-link.active')?.getAttribute('aria-controls') || 'overview';
    
    if (userId && userName) {
      if (confirm(`Are you sure you want to remove ${userName}?`)) {
        // Determine which API to use based on button class
        const isCompleteRemoval = button.classList.contains('complete-remove-btn');
        const apiEndpoint = isCompleteRemoval 
          ? `/admin/api-complete-remove-user/${userId}`
          : `/api/remove-user/${userId}`;
        
        // API call
        fetch(apiEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        }).then(response => {
          if (response.ok) {
            // Redirect with tab parameter to preserve current tab
            window.location.href = `/admin?tab=${currentTab}`;
          } else {
            return response.json().then(data => {
              throw new Error(data.error || 'Failed to remove participant');
            });
          }
        }).catch(error => {
          console.error('Error:', error);
          alert(`Error removing participant: ${error.message}. Please try again.`);
        });
      }
    }
  }
  
  // Add visual feedback for clickable rows
  function addRowStyling() {
    document.querySelectorAll('tr[data-participant-id]').forEach(row => {
      // Check if row has remove buttons
      const hasRemoveButtons = row.querySelector('.remove-participant-btn, .complete-remove-btn');
      
      if (!hasRemoveButtons) {
        // Row is clickable - add class and tooltip
        row.classList.add('clickable-row');
        row.title = 'Click to remove this participant';
      } else {
        // Row has buttons - remove clickable styling
        row.classList.remove('clickable-row');
        row.removeAttribute('title');
      }
    });
  }
  
  // Add event listeners
  document.addEventListener('DOMContentLoaded', function() {
    // Add click listeners to participant rows
    document.addEventListener('click', handleParticipantRemoval);
    
    // Add specific button click handlers
    document.addEventListener('click', handleButtonClick);
    
    // Add styling to rows
    addRowStyling();
    
    // Re-apply styling when content changes (for dynamic content)
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
          addRowStyling();
        }
      });
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();

