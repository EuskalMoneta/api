var config = {};
config.getCSRFToken = '{{ csrf_token }}';
config.getAPIBaseURL = '{{ django_settings.API_URL }}';
window.config = config;