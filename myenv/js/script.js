document.getElementById('registrationForm').addEventListener('submit', function(event) {
    event.preventDefault();
    
    const formData = {
        name: document.getElementById('name').value,
        email: document.getElementById('email').value,
        department: document.getElementById('department').value,
        class: document.getElementById('class').value,
        college: document.getElementById('college').value,
        year: document.getElementById('year').value,
        phone: document.getElementById('phone').value
    };

    // Save formData to localStorage or send to a server
    localStorage.setItem('participantData', JSON.stringify(formData));
    
    alert('Registration Successful!');
    window.location.href = 'dashboard.html'; // Redirect to dashboard
});