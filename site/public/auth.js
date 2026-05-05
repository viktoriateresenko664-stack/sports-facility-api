document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            
            if (!email || !password) {
                showToast('Заполните все поля!', 'error');
                return;
            }

            if (typeof window.login === 'function') {
                window.login(email, password);
            } else {
                console.error('login function not found');
                showToast('Ошибка: функция входа не найдена', 'error');
            }
        });
    }

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const confirm = document.getElementById('confirmPassword').value;
            
            if (password !== confirm) {
                showToast('Пароли не совпадают!', 'error');
                return;
            }
            
            const userData = {
                username: document.getElementById('username').value,
                email: document.getElementById('email').value,
                password: password,
                phone: document.getElementById('phone').value,
                role: 'user'
            };

            if (typeof window.register === 'function') {
                window.register(userData);
            } else {
                console.error('register function not found');
                showToast('Ошибка: функция регистрации не найдена', 'error');
            }
        });
    }
});