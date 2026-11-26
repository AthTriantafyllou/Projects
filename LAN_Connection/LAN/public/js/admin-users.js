document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('usersManagerModal');
    const openButton = document.getElementById('openUsersManager');
    const closeButtons = document.querySelectorAll('[data-close-users-modal]');
    const modalPanel = modal.querySelector('.users-modal-panel');

    const message = document.getElementById('usersManagerMessage');
    const usersList = document.getElementById('usersManagerList');

    const addUserButton = document.getElementById('addNewUserButton');
    const createSection = document.getElementById('createUserSection');
    const createForm = document.getElementById('createUserForm');

    const csrfToken = createForm.elements.CSRFToken.value;

    let previousFocus = null;

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.classList.toggle('is-error', isError);
        message.hidden = !text;
    }

    function openModal() {
        previousFocus = document.activeElement;
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        loadUsers();
        modalPanel.focus();
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = '';

        if (previousFocus) {
            previousFocus.focus();
        }
    }

    openButton.addEventListener('click', openModal);

    closeButtons.forEach(button => {
        button.addEventListener('click', closeModal);
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !modal.hidden) {
            closeModal();
        }
    });

    addUserButton.addEventListener('click', () => {
        createSection.hidden = !createSection.hidden;

        if (!createSection.hidden) {
            createForm.elements.username.focus();
        }
    });

    async function postForm(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams(formData)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Η ενέργεια απέτυχε.');
        }

        return result;
    }

    async function loadUsers() {
        usersList.replaceChildren();
        showMessage('');

        const loading = document.createElement('p');
        loading.textContent = 'Φόρτωση χρηστών…';
        usersList.appendChild(loading);

        try {
            const response = await fetch('/admin/users', {
                credentials: 'same-origin'
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Αποτυχία φόρτωσης χρηστών.');
            }

            renderUsers(result.users || []);
        } catch (error) {
            usersList.replaceChildren();

            const errorText = document.createElement('p');
            errorText.textContent = error.message || 'Παρουσιάστηκε σφάλμα.';
            usersList.appendChild(errorText);
        }
    }

    function renderUsers(users) {
        usersList.replaceChildren();

        if (users.length === 0) {
            const empty = document.createElement('p');
            empty.textContent = 'Δεν υπάρχουν χρήστες.';
            usersList.appendChild(empty);
            return;
        }

        const table = document.createElement('table');
        table.className = 'users-table';

        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');

        ['#', 'Username', 'Τύπος', 'Ενέργεια'].forEach(title => {
            const th = document.createElement('th');
            th.textContent = title;
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');

        users.forEach((user, index) => {
            const row = document.createElement('tr');

            const numberCell = document.createElement('td');
            numberCell.textContent = String(index + 1);

            const usernameCell = document.createElement('td');
            usernameCell.textContent = user.username;

            const roleCell = document.createElement('td');
            roleCell.textContent = {
                user: 'User',
                admin: 'Admin',
                safety_admin: 'Safety Admin'
            }[user.role] || user.role;

            const actionCell = document.createElement('td');

            if (user.role === 'user') {
                const deleteButton = document.createElement('button');
                deleteButton.type = 'button';
                deleteButton.textContent = 'Delete';
                deleteButton.className = 'user-delete-button';

                deleteButton.addEventListener('click', async () => {
                    const confirmed = window.confirm(
                        `Να διαγραφεί ο χρήστης "${user.username}";`
                    );

                    if (!confirmed) {
                        return;
                    }

                    deleteButton.disabled = true;
                    showMessage('');

                    try {
                        await postForm(
                            `/admin/users/${user.id}/delete`,
                            { CSRFToken: csrfToken }
                        );

                        showMessage('Ο χρήστης διαγράφηκε.');
                        await loadUsers();
                    } catch (error) {
                        showMessage(
                            error.message || 'Αποτυχία διαγραφής χρήστη.',
                            true
                        );
                        deleteButton.disabled = false;
                    }
                });

                actionCell.appendChild(deleteButton);
            } else {
                actionCell.textContent = '—';
            }

            row.append(numberCell, usernameCell, roleCell, actionCell);
            tbody.appendChild(row);
        });

        table.appendChild(tbody);
        usersList.appendChild(table);
    }

    createForm.addEventListener('submit', async event => {
        event.preventDefault();
        showMessage('');

        const submitButton = createForm.querySelector('[type="submit"]');
        submitButton.disabled = true;

        const formData = new FormData(createForm);

        try {
            await postForm('/admin/users/create', formData);

            createForm.reset();
            createSection.hidden = true;

            showMessage('Ο χρήστης δημιουργήθηκε επιτυχώς.');
            await loadUsers();
        } catch (error) {
            showMessage(
                error.message || 'Αποτυχία δημιουργίας χρήστη.',
                true
            );
        } finally {
            submitButton.disabled = false;
        }
    });
});