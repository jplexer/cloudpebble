CloudPebble.Publish = (function() {
    var mPreflightData = null;
    var mScreenshots = {}; // {platform: [{type: 'png'|'gif', blob: Blob, url: dataURL}, ...]}
    var mCapturing = false;
    var mInitialized = false;

    // Deferred lookup — ConnectionType is defined in pebble.js which may load after this file
    function getConnectionType(platform) {
        var map = {
            'aplite': ConnectionType.QemuAplite,
            'basalt': ConnectionType.QemuBasalt,
            'chalk': ConnectionType.QemuChalk,
            'diorite': ConnectionType.QemuDiorite,
            'emery': ConnectionType.QemuEmery,
            'gabbro': ConnectionType.QemuGabbro,
            'flint': ConnectionType.QemuFlint
        };
        return map[platform];
    }

    function getPlatforms() {
        var platforms = CloudPebble.ProjectInfo.app_platforms;
        if (!platforms) return [];
        return platforms.split(',').filter(function(p) { return p.trim().length > 0; });
    }

    function showError(message) {
        $('#publish-error').text(message).removeClass('hide').addClass('alert-error');
    }

    function hideError() {
        $('#publish-error').addClass('hide');
    }

    function setStatus(text) {
        $('#publish-status-text').text(text);
    }

    function preflight() {
        hideError();
        $('#publish-status-area').show();
        $('#publish-preflight-progress').show();
        $('#publish-form-area').hide();
        $('#publish-success').addClass('hide');
        setStatus('Checking app store status...');

        Ajax.Post('/ide/project/' + PROJECT_ID + '/publish/preflight')
            .then(function(data) {
                mPreflightData = data;
                $('#publish-preflight-progress').hide();

                if (data.is_new_app) {
                    setStatus('This app has not been published yet. Fill in the details below to publish it.');
                    showNewAppFields(data);
                } else {
                    setStatus('This app is already in the store (ID: ' + data.app_id + '). You can publish an update.');
                    hideNewAppFields();
                }

                $('#publish-form-area').show();
                updatePublishButton();
            })
            .catch(function(error) {
                $('#publish-preflight-progress').hide();
                setStatus('Could not check app store status.');
                showError(error.message);
            });
    }

    function showNewAppFields(data) {
        $('#publish-new-app-fields').show();
        $('#publish-name').val(data.app_name || '');
        $('#publish-version').val(data.app_version || '1.0');

        if (data.github_repo) {
            $('#publish-source').val('https://github.com/' + data.github_repo);
        }

        // Category dropdown for watchapps only
        if (!data.is_watchface) {
            var select = $('#publish-category').empty();
            select.append($('<option value="">').text('Select a category...'));
            _.each(data.category_options, function(opt) {
                select.append($('<option>').val(opt.value).text(opt.label));
            });
            $('#publish-category-group').show();
            $('#publish-icon-group').show();
        } else {
            $('#publish-category-group').hide();
            $('#publish-icon-group').hide();
        }

        $('#publish-screenshot-hint').text(
            'At least one screenshot is required for new apps. Click "Capture Screenshots" to automatically capture from the emulator.'
        );
    }

    function hideNewAppFields() {
        $('#publish-new-app-fields').hide();
        $('#publish-screenshot-hint').text(
            'Optionally capture new screenshots to include with this update.'
        );
    }

    function updatePublishButton() {
        var btn = $('#publish-submit-btn');
        var noBuildMsg = $('#publish-no-build-msg');
        if (!mPreflightData) {
            btn.attr('disabled', 'disabled').hide();
            noBuildMsg.hide();
            return;
        }

        if (!mPreflightData.has_successful_build) {
            btn.attr('disabled', 'disabled').hide();
            noBuildMsg.show();
            return;
        }

        noBuildMsg.hide();
        btn.show();

        if (mPreflightData.is_new_app) {
            btn.text('Publish to App Store');
            var name = $('#publish-name').val().trim();
            var description = $('#publish-description').val().trim();
            var hasScreenshots = _.some(mScreenshots, function(list) { return list.length > 0; });
            var needsCategory = !mPreflightData.is_watchface;
            var category = $('#publish-category').val();

            if (name && description && hasScreenshots && (!needsCategory || category)) {
                btn.removeAttr('disabled');
            } else {
                btn.attr('disabled', 'disabled');
            }
        } else {
            btn.text('Publish Update');
            btn.removeAttr('disabled');
        }
    }

    function buildScreenshotPlatformUI() {
        var container = $('#publish-screenshot-platforms').empty();
        var platforms = getPlatforms();

        _.each(platforms, function(platform) {
            var section = $('<div class="publish-screenshot-platform">')
                .attr('data-platform', platform);
            section.append($('<strong>').text(platform));
            section.append($('<div class="publish-screenshot-thumbs">'));
            container.append(section);
        });
    }

    function updateScreenshotThumbs() {
        var container = $('#publish-screenshot-platforms');
        var platforms = getPlatforms();

        _.each(platforms, function(platform) {
            var section = container.find('[data-platform="' + platform + '"]');
            var thumbs = section.find('.publish-screenshot-thumbs').empty();
            var items = mScreenshots[platform] || [];

            _.each(items, function(item, index) {
                var thumb = $('<div class="publish-screenshot-thumb">');
                thumb.append($('<img>').attr('src', item.url).css({maxWidth: '80px', maxHeight: '80px'}));
                thumb.append($('<span class="muted">').text(' ' + item.type.toUpperCase()));
                var removeBtn = $('<a href="#" class="muted" style="margin-left: 4px;">').text('[x]');
                removeBtn.click(function(e) {
                    e.preventDefault();
                    items.splice(index, 1);
                    updateScreenshotThumbs();
                    updatePublishButton();
                });
                thumb.append(removeBtn);
                thumbs.append(thumb);
            });
        });
    }

    function captureScreenshots() {
        if (mCapturing) return;
        mCapturing = true;

        var platforms = getPlatforms();
        var captureBtn = $('#publish-capture-btn').attr('disabled', 'disabled');
        var statusEl = $('#publish-capture-status');
        mScreenshots = {};

        var chain = Promise.resolve();
        _.each(platforms, function(platform) {
            chain = chain.then(function() {
                return captureForPlatform(platform, statusEl);
            });
        });

        chain.then(function() {
            statusEl.text('Done!');
            updateScreenshotThumbs();
            updatePublishButton();
        }).catch(function(error) {
            statusEl.text('Error: ' + error.message);
            showError('Screenshot capture failed: ' + error.message);
        }).finally(function() {
            mCapturing = false;
            captureBtn.removeAttr('disabled');
        });
    }

    function captureForPlatform(platform, statusEl) {
        var connectionType = getConnectionType(platform);
        if (!connectionType) {
            return Promise.reject(new Error('Unknown platform: ' + platform));
        }

        statusEl.text('Booting emulator for ' + platform + '...');

        return SharedPebble.getPebble(connectionType).then(function(pebble) {
            return Ajax.Get('/ide/project/' + PROJECT_ID + '/build/last').then(function(data) {
                if (!data.build || data.build.state !== 3) {
                    throw new Error('No successful build available. Please build first.');
                }
                statusEl.text('Installing app on ' + platform + '...');

                return new Promise(function(resolve, reject) {
                    var installTimeout = setTimeout(function() {
                        pebble.off('status', onStatus);
                        pebble.off('error', onError);
                        reject(new Error('Install timed out on ' + platform));
                    }, 30000);
                    function onStatus(code) {
                        clearTimeout(installTimeout);
                        pebble.off('status', onStatus);
                        pebble.off('error', onError);
                        if (code === 0) {
                            resolve(pebble);
                        } else {
                            reject(new Error('Install failed on ' + platform));
                        }
                    }
                    function onError(e) {
                        clearTimeout(installTimeout);
                        pebble.off('status', onStatus);
                        pebble.off('error', onError);
                        reject(new Error('Install error on ' + platform + ': ' + e));
                    }
                    pebble.on('status', onStatus);
                    pebble.on('error', onError);
                    pebble.install_app(data.build.download);
                });
            });
        }).then(function(pebble) {
            // Wait for app to settle after install
            return Promise.delay(2000).then(function() { return pebble; });
        }).then(function(pebble) {
            // Press the back button every 1s to keep the backlight on during capture
            var backlightInterval = setInterval(function() {
                try {
                    pebble.emu_press_button(Pebble.Button.Back, true);
                    setTimeout(function() {
                        pebble.emu_press_button(Pebble.Button.Back, false);
                    }, 100);
                } catch (e) {
                    // Ignore errors if emulator disconnects
                }
            }, 1000);

            function clearBacklight() {
                clearInterval(backlightInterval);
            }

            statusEl.text('Taking screenshot on ' + platform + '...');

            return new Promise(function(resolve, reject) {
                var timeout = setTimeout(function() {
                    pebble.off('screenshot:complete');
                    pebble.off('screenshot:failed');
                    reject(new Error('Screenshot timed out on ' + platform));
                }, 15000);

                pebble.once('screenshot:complete', function(imgElement) {
                    clearTimeout(timeout);
                    resolve(imgElement);
                });
                pebble.once('screenshot:failed', function(reason) {
                    clearTimeout(timeout);
                    reject(new Error('Screenshot failed: ' + reason));
                });
                pebble.request_screenshot();
            }).then(function(imgElement) {
                var dataUrl = imgElement.src || $(imgElement).attr('src');
                return dataURLtoBlob(dataUrl).then(function(blob) {
                    if (!mScreenshots[platform]) mScreenshots[platform] = [];
                    mScreenshots[platform].push({
                        type: 'png',
                        blob: blob,
                        url: dataUrl
                    });
                });
            }).then(function() {
                // Record GIF from VNC canvas
                var canvas = $('#emulator-container canvas')[0];
                if (!canvas) {
                    console.warn('No VNC canvas available for GIF recording on ' + platform);
                    return;
                }

                statusEl.text('Recording GIF on ' + platform + ' (5s)...');
                return recordGif(canvas, 5000, 10).then(function(gifBlob) {
                    var gifUrl = URL.createObjectURL(gifBlob);
                    if (!mScreenshots[platform]) mScreenshots[platform] = [];
                    mScreenshots[platform].push({
                        type: 'gif',
                        blob: gifBlob,
                        url: gifUrl
                    });
                });
            }).then(function() {
                clearBacklight();
                statusEl.text('Done with ' + platform + '.');
                updateScreenshotThumbs();
            }, function(err) {
                clearBacklight();
                throw err;
            });
        });
    }

    function recordGif(canvas, durationMs, fps) {
        var workerUrl = (typeof GIF_WORKER_URL !== 'undefined') ? GIF_WORKER_URL : '/static/ide/external/gif.worker.js';
        var gif = new GIF({
            workers: 2,
            quality: 10,
            width: canvas.width,
            height: canvas.height,
            workerScript: workerUrl
        });
        var interval = 1000 / fps;

        var timer = setInterval(function() {
            var frame = document.createElement('canvas');
            frame.width = canvas.width;
            frame.height = canvas.height;
            frame.getContext('2d').drawImage(canvas, 0, 0);
            gif.addFrame(frame, {delay: interval, copy: true});
        }, interval);

        return new Promise(function(resolve) {
            setTimeout(function() {
                clearInterval(timer);
                gif.on('finished', function(blob) {
                    resolve(blob);
                });
                gif.render();
            }, durationMs);
        });
    }

    function dataURLtoBlob(dataUrl) {
        return new Promise(function(resolve) {
            var parts = dataUrl.split(',');
            var mime = parts[0].match(/:(.*?);/)[1];
            var bstr = atob(parts[1]);
            var n = bstr.length;
            var u8arr = new Uint8Array(n);
            for (var i = 0; i < n; i++) {
                u8arr[i] = bstr.charCodeAt(i);
            }
            resolve(new Blob([u8arr], {type: mime}));
        });
    }

    function submitPublish(e) {
        e.preventDefault();
        if (!mPreflightData) return;

        var btn = $('#publish-submit-btn').attr('disabled', 'disabled');
        var statusEl = $('#publish-submit-status').text('Publishing...');
        hideError();
        $('#publish-success').addClass('hide');

        var formData = new FormData();
        formData.append('is_new_app', mPreflightData.is_new_app ? 'true' : 'false');
        formData.append('app_id', mPreflightData.app_id || '');

        if (mPreflightData.is_new_app) {
            formData.append('name', $('#publish-name').val().trim());
            formData.append('version', $('#publish-version').val().trim());
            formData.append('description', $('#publish-description').val().trim());
            formData.append('source', $('#publish-source').val().trim());
            formData.append('category', $('#publish-category').val() || '');
        }

        formData.append('release_notes', $('#publish-release-notes').val().trim());

        // Add icon files if uploading
        var iconMode = $('input[name="publish-icon-mode"]:checked').val();
        if (iconMode === 'upload') {
            var smallIcon = $('#publish-icon-small')[0];
            var largeIcon = $('#publish-icon-large')[0];
            if (smallIcon && smallIcon.files[0]) formData.append('icon_small', smallIcon.files[0]);
            if (largeIcon && largeIcon.files[0]) formData.append('icon_large', largeIcon.files[0]);
        }

        // Add screenshots — each file gets a unique field name
        var screenshotIndex = 0;
        _.each(mScreenshots, function(items, platform) {
            _.each(items, function(item) {
                var ext = item.type === 'gif' ? '.gif' : '.png';
                formData.append(
                    'screenshot_' + platform + '_' + screenshotIndex,
                    item.blob,
                    'screenshot_' + platform + '_' + screenshotIndex + ext
                );
                screenshotIndex++;
            });
        });

        $.ajax({
            url: '/ide/project/' + PROJECT_ID + '/publish/submit',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            dataType: 'json'
        }).then(function(data) {
            if (data.success) {
                statusEl.text('');
                $('#publish-success').removeClass('hide');
                if (data.app_url) {
                    $('#publish-app-link').attr('href', data.app_url).text('View on App Store');
                } else if (data.app_id) {
                    var storeUrl = 'https://apps.repebble.com/en_US/application/' + data.app_id;
                    $('#publish-app-link').attr('href', storeUrl).text('View on App Store');
                } else {
                    $('#publish-app-link').hide();
                }
            } else {
                statusEl.text('');
                showError(data.error || 'Publishing failed.');
            }
            btn.removeAttr('disabled');
        }).fail(function(jqXHR) {
            var message = 'Publishing failed.';
            if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
                message = jqXHR.responseJSON.error;
            }
            statusEl.text('');
            showError(message);
            btn.removeAttr('disabled');
        });
    }

    function initPane() {
        if (mInitialized) return;
        mInitialized = true;

        var pane = $('#publish-pane-template');

        pane.find('#publish-capture-btn').click(function(e) {
            e.preventDefault();
            captureScreenshots();
        });
        pane.find('#publish-form').submit(submitPublish);

        // Update publish button when form fields change
        pane.find('#publish-name, #publish-description, #publish-category').on('input change', updatePublishButton);

        // Toggle icon upload fields
        pane.find('input[name="publish-icon-mode"]').change(function() {
            if ($(this).val() === 'upload') {
                pane.find('#publish-icon-uploads').show();
            } else {
                pane.find('#publish-icon-uploads').hide();
            }
        });
    }

    return {
        Show: function() {
            CloudPebble.Sidebar.SuspendActive();
            if (CloudPebble.Sidebar.Restore('publish')) {
                return;
            }
            initPane();
            buildScreenshotPlatformUI();
            CloudPebble.Sidebar.SetActivePane($('#publish-pane-template').show(), {id: 'publish'});
            preflight();
        },
        Init: function() {
            // Nothing to initialize at startup
        }
    };
})();
