const signUpButton = document.getElementById('signUp');
const signInButton = document.getElementById('signIn');
const container = document.getElementById('container');

signUpButton.addEventListener('click', () =>
container.classList.add('right-panel-active'));

signInButton.addEventListener('click', () =>
container.classList.remove('right-panel-active'));
function redirectToHome() {
    window.location.href = "{% url 'index' %}";  // Replace 'index' with the actual name of your home URL
}

