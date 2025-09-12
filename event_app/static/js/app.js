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
    
    // Don't trigger on form elements or buttons
    if (event.target.closest('form, button, input, select, textarea, a')) return;
    
    const participantId = participantRow.getAttribute('data-participant-id');
    const participantName = participantRow.getAttribute('data-participant-name');
    
    if (participantId && participantName) {
      if (confirm(`Click to remove: Are you sure you want to remove ${participantName}?`)) {
        // Find and submit the remove form
        const removeForm = document.querySelector(`form[action*="/admin/user/remove/${participantId}"]`);
        if (removeForm) {
          removeForm.submit();
        } else {
          // If no form found, try to make a direct request
          fetch(`/admin/user/remove/${participantId}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            }
          }).then(response => {
            if (response.ok) {
              location.reload(); // Refresh page to show updated data
            } else {
              alert('Failed to remove participant. Please try again.');
            }
          }).catch(error => {
            console.error('Error:', error);
            alert('Error removing participant. Please try again.');
          });
        }
      }
    }
  }
  
  // Add visual feedback for clickable rows
  function addRowStyling() {
    document.querySelectorAll('tr[data-participant-id]').forEach(row => {
      row.style.cursor = 'pointer';
      row.title = 'Click to remove this participant';
      
      // Add hover effect
      row.addEventListener('mouseenter', function() {
        this.style.backgroundColor = '#fff3cd';
      });
      
      row.addEventListener('mouseleave', function() {
        this.style.backgroundColor = '';
      });
    });
  }
  
  // Add event listeners
  document.addEventListener('DOMContentLoaded', function() {
    // Add click listeners to participant rows
    document.addEventListener('click', handleParticipantRemoval);
    
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

