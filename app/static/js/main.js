document.addEventListener('DOMContentLoaded', function () {
    // Login toggle
    var toggle = document.getElementById('login-toggle');
    var form = document.getElementById('login-form');
    if (toggle && form) {
        toggle.addEventListener('click', function () {
            form.classList.toggle('hidden');
            if (!form.classList.contains('hidden')) {
                form.querySelector('input').focus();
            }
        });
    }

    // Inline editing
    var indicator = document.createElement('div');
    indicator.className = 'save-indicator';
    indicator.textContent = 'Saved';
    document.body.appendChild(indicator);

    var editableCells = document.querySelectorAll('td[contenteditable="true"]');
    editableCells.forEach(function (cell) {
        cell.dataset.original = cell.textContent;

        cell.addEventListener('focus', function () {
            this.dataset.original = this.textContent;
        });

        cell.addEventListener('blur', function () {
            var newVal = this.textContent.trim();
            if (newVal === this.dataset.original) return;

            var row = this.closest('tr');
            var id = row.dataset.id;
            var field = this.dataset.field;
            var body = {};
            body[field] = newVal;

            fetch('/api/cultivar/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
            .then(function (res) {
                if (!res.ok) throw new Error('Save failed');
                return res.json();
            })
            .then(function () {
                indicator.textContent = 'Saved';
                indicator.className = 'save-indicator show';
                setTimeout(function () { indicator.className = 'save-indicator'; }, 1500);
            })
            .catch(function () {
                indicator.textContent = 'Error saving';
                indicator.className = 'save-indicator show error';
                setTimeout(function () { indicator.className = 'save-indicator'; }, 2500);
            });
        });

        // Save on Enter, prevent newline
        cell.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.blur();
            }
        });
    });

    // Image URL inputs
    var imgInputs = document.querySelectorAll('.img-url-input');
    imgInputs.forEach(function (input) {
        input.dataset.original = input.value;

        input.addEventListener('focus', function () {
            this.dataset.original = this.value;
        });

        input.addEventListener('blur', function () {
            var newVal = this.value.trim();
            if (newVal === this.dataset.original) return;

            var row = this.closest('tr');
            var id = row.dataset.id;
            var self = this;

            fetch('/api/cultivar/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_url: newVal })
            })
            .then(function (res) {
                if (!res.ok) throw new Error('Save failed');
                return res.json();
            })
            .then(function () {
                // Update the image preview
                var td = self.closest('td');
                var img = td.querySelector('img');
                if (newVal) {
                    if (!img) {
                        img = document.createElement('img');
                        img.loading = 'lazy';
                        img.alt = '';
                        td.insertBefore(img, self);
                    }
                    img.src = newVal;
                } else if (img) {
                    img.remove();
                }
                indicator.textContent = 'Saved';
                indicator.className = 'save-indicator show';
                setTimeout(function () { indicator.className = 'save-indicator'; }, 1500);
            })
            .catch(function () {
                indicator.textContent = 'Error saving';
                indicator.className = 'save-indicator show error';
                setTimeout(function () { indicator.className = 'save-indicator'; }, 2500);
            });
        });

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.blur();
            }
        });
    });
});

function changePerPage(val) {
    var url = new URL(window.location);
    url.searchParams.set('per_page', val);
    url.searchParams.set('page', '1');
    window.location = url;
}
