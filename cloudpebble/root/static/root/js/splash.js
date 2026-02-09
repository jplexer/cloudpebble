$(function() {
    jquery_csrf_setup();

    firebase.initializeApp({
        apiKey: "AIzaSyBZ9Cdvwwv9At2lPmc8TxyyEqSXGXejGvc",
        authDomain: "coreapp-ce061.firebaseapp.com",
        projectId: "coreapp-ce061",
        storageBucket: "coreapp-ce061.firebasestorage.app",
        messagingSenderId: "460977838956",
        appId: "1:460977838956:web:9a11a68ec78008fe303149",
        measurementId: "G-J99JXFWEZL"
    });

    var gMainContent = $('.main-container');

    $('.btn-show-login').click(function() {
        gMainContent.addClass('show-login');
    });

    $('.btn-hide-login').click(function() {
        gMainContent.removeClass('show-login');
    });

    if(location.hash == '#login') {
        gMainContent.addClass('show-login');
    }

    $('#firebase-login-btn').click(function() {
        $('#provider-chooser').modal('show');
    });

    $('.provider-btn').click(function() {
        var providerName = $(this).data('provider');
        var provider;
        if (providerName === 'google') {
            provider = new firebase.auth.GoogleAuthProvider();
        } else if (providerName === 'github') {
            provider = new firebase.auth.GithubAuthProvider();
        } else if (providerName === 'apple') {
            provider = new firebase.auth.OAuthProvider('apple.com');
        }

        $('#provider-chooser').find('.btn').attr('disabled', 'disabled');

        firebase.auth().signInWithPopup(provider).then(function(result) {
            return result.user.getIdToken();
        }).then(function(idToken) {
            return Ajax.Post('/accounts/api/firebase-login', {
                id_token: idToken
            });
        }).then(function() {
            location.href = '/ide/';
        }).catch(function(error) {
            if (error.code !== 'auth/popup-closed-by-user') {
                alert(error.message || error);
            }
        }).finally(function() {
            $('#provider-chooser').find('.btn').removeAttr('disabled');
        });
    });
});
