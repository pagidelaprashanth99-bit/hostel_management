// Set minimum date for appointment booking
document.addEventListener('DOMContentLoaded', function() {
    const appointmentDateInput = document.getElementById('appointment_date');
    if (appointmentDateInput && !appointmentDateInput.getAttribute('min')) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        appointmentDateInput.setAttribute('min', tomorrow.toISOString().split('T')[0]);
    }
});

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

