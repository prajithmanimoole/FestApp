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

// Right-click context menu for removing participants
(function(){
  let contextMenu = null;
  
  // Create context menu
  function createContextMenu() {
    if (contextMenu) return contextMenu;
    
    contextMenu = document.createElement('div');
    contextMenu.id = 'participantContextMenu';
    contextMenu.className = 'context-menu';
    contextMenu.innerHTML = `
      <div class="context-menu-item" data-action="remove">
        <i class="fas fa-trash"></i> Remove Participant
      </div>
    `;
    document.body.appendChild(contextMenu);
    return contextMenu;
  }
  
  // Show context menu
  function showContextMenu(event, participantId, participantName) {
    event.preventDefault();
    event.stopPropagation();
    
    const menu = createContextMenu();
    menu.style.display = 'block';
    menu.style.left = event.pageX + 'px';
    menu.style.top = event.pageY + 'px';
    menu.setAttribute('data-participant-id', participantId);
    menu.setAttribute('data-participant-name', participantName);
    
    // Position menu within viewport
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (event.pageX - rect.width) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (event.pageY - rect.height) + 'px';
    }
  }
  
  // Hide context menu
  function hideContextMenu() {
    if (contextMenu) {
      contextMenu.style.display = 'none';
    }
  }
  
  // Handle context menu actions
  function handleContextAction(event) {
    const action = event.target.closest('.context-menu-item')?.getAttribute('data-action');
    if (!action) return;
    
    const participantId = contextMenu.getAttribute('data-participant-id');
    const participantName = contextMenu.getAttribute('data-participant-name');
    
    if (action === 'remove' && participantId) {
      if (confirm(`Are you sure you want to remove ${participantName}?`)) {
        // Find and submit the remove form
        const removeForm = document.querySelector(`form[action*="/admin/user/remove/${participantId}"]`);
        if (removeForm) {
          removeForm.submit();
        }
      }
    }
    
    hideContextMenu();
  }
  
  // Add event listeners
  document.addEventListener('DOMContentLoaded', function() {
    // Add right-click listeners to participant rows
    document.addEventListener('contextmenu', function(event) {
      const participantRow = event.target.closest('tr[data-participant-id]');
      if (participantRow) {
        const participantId = participantRow.getAttribute('data-participant-id');
        const participantName = participantRow.getAttribute('data-participant-name');
        showContextMenu(event, participantId, participantName);
      }
    });
    
    // Hide context menu on click outside
    document.addEventListener('click', hideContextMenu);
    
    // Handle context menu actions
    document.addEventListener('click', handleContextAction);
    
    // Hide context menu on escape key
    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') {
        hideContextMenu();
      }
    });
  });
})();

