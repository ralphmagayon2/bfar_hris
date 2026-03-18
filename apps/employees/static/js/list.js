function submitChip(type) {
    // Set the hidden input value to the chosen type
    document.getElementById('type-input').value = type;
    // Submit the form to Django
    document.getElementById('filter-form').submit();
}