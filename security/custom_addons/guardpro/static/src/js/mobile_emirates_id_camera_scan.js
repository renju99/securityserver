/* GuardPro mobile PWA: Emirates ID camera capture + server OCR (plain script, web.assets_frontend). */

/**
 * Global entry for inline onclick (reliable on Android Chrome/WebView). Assigned before the IIFE
 * so the attribute works as soon as this file is parsed.
 */
window.guardproEidTriggerScan = function (ev, el) {
    'use strict';
    if (ev && typeof ev.preventDefault === 'function') {
        ev.preventDefault();
    }
    if (ev && typeof ev.stopPropagation === 'function') {
        ev.stopPropagation();
    }
    if (typeof window.__guardproEidRunScan === 'function') {
        return window.__guardproEidRunScan(ev, el);
    }
    alert(
        'Scanner is still loading. Pull down to refresh the page, wait a few seconds, then tap again.'
    );
    return false;
};

(function () {
    'use strict';

    var OCR_URL = '/guardpro/api/visitor/emirates_id_ocr';

    function jsonRpc(url, params) {
        return fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: params,
                id: Date.now(),
            }),
        }).then(function (res) {
            return res.json();
        }).then(function (data) {
            if (data.error) {
                var msg =
                    (data.error.data && data.error.data.message) ||
                    (data.error.data && data.error.data.debug) ||
                    data.error.message ||
                    'RPC error';
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            return data.result;
        });
    }

    function dataUrlToRawB64(dataUrl) {
        var i = dataUrl.indexOf(',');
        return i >= 0 ? dataUrl.slice(i + 1) : dataUrl;
    }

    function setFormField(formRoot, field, val) {
        if (val === undefined || val === null || val === '') {
            return;
        }
        var cleanVal = String(val).replace(/,/g, ' ').replace(/\s+/g, ' ').trim();
        if (!cleanVal || !formRoot) {
            return;
        }
        var input = formRoot.querySelector('[name="' + field + '"]');
        if (!input) {
            return;
        }
        try {
            if (input.tagName === 'SELECT') {
                var optionIndex = -1;
                for (var oi = 0; oi < input.options.length; oi++) {
                    var opt = input.options[oi];
                    if (opt.value === cleanVal) {
                        optionIndex = oi;
                        break;
                    }
                }
                if (optionIndex !== -1) {
                    input.selectedIndex = optionIndex;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            } else {
                input.value = cleanVal;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } catch (e) {
            console.warn('[GuardPro Mobile EID] set field failed', field, e);
        }
    }

    function setIdPhotoHidden(formRoot, b64) {
        if (!b64 || !formRoot) {
            return;
        }
        var hidden = formRoot.querySelector('input[name="id_photo"]');
        if (hidden) {
            hidden.value = b64;
            hidden.dispatchEvent(new Event('input', { bubbles: true }));
            hidden.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function injectStyles() {
        if (document.getElementById('guardpro-mobile-eid-scan-styles')) {
            return;
        }
        var style = document.createElement('style');
        style.id = 'guardpro-mobile-eid-scan-styles';
        style.textContent =
            '.guardpro-mobile-eid-overlay{position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;font-family:system-ui,sans-serif}' +
            '.guardpro-mobile-eid-modal{background:#fff;border-radius:8px;max-width:520px;width:94%;height:min(92vh,760px);display:flex;flex-direction:column;overflow:hidden;padding:12px;box-shadow:0 8px 32px rgba(0,0,0,.2)}' +
            '.guardpro-mobile-eid-modal h3{margin:0 0 8px;font-size:1.1rem}' +
            '.guardpro-mobile-eid-sub{margin:0 0 10px;font-size:13px;color:#666;flex:0 0 auto}' +
            '.guardpro-mobile-eid-body{flex:1 1 auto;overflow:auto;min-height:0;padding-bottom:8px}' +
            '.guardpro-mobile-eid-camera-wrap{position:relative;width:100%;border-radius:6px;overflow:hidden;background:#000}' +
            '.guardpro-mobile-eid-modal video{width:100%;display:block;max-height:50vh;aspect-ratio:16/10;object-fit:cover;border-radius:6px;background:#000}' +
            '.guardpro-mobile-eid-guide{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:84%;aspect-ratio:1.586;border-radius:10px;box-shadow:0 0 0 2000px rgba(0,0,0,.35);pointer-events:none}' +
            '.guardpro-mobile-eid-guide::before,.guardpro-mobile-eid-guide::after{content:"";position:absolute;inset:0;border-radius:10px;border:2px solid rgba(255,255,255,.85)}' +
            '.guardpro-mobile-eid-guide .corner{position:absolute;width:24px;height:24px;border-color:#39d353;border-style:solid;border-width:0}' +
            '.guardpro-mobile-eid-guide .tl{top:-1px;left:-1px;border-top-width:4px;border-left-width:4px;border-top-left-radius:8px}' +
            '.guardpro-mobile-eid-guide .tr{top:-1px;right:-1px;border-top-width:4px;border-right-width:4px;border-top-right-radius:8px}' +
            '.guardpro-mobile-eid-guide .bl{bottom:-1px;left:-1px;border-bottom-width:4px;border-left-width:4px;border-bottom-left-radius:8px}' +
            '.guardpro-mobile-eid-guide .br{bottom:-1px;right:-1px;border-bottom-width:4px;border-right-width:4px;border-bottom-right-radius:8px}' +
            '.guardpro-mobile-eid-modal .preview img{width:100%;max-height:46vh;object-fit:contain;border-radius:6px;border:1px solid #ddd}' +
            '.guardpro-mobile-eid-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid #ececec;flex:0 0 auto;position:sticky;bottom:0;background:#fff;z-index:2}' +
            '.guardpro-mobile-eid-actions button{flex:1;min-width:100px;padding:10px 12px;border-radius:6px;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;font-weight:600}' +
            '.guardpro-mobile-eid-actions button.primary{background:#714B67;color:#fff;border-color:#714B67}' +
            '.guardpro-mobile-eid-actions button.danger{background:#dc3545;color:#fff;border-color:#dc3545}' +
            '.guardpro-mobile-eid-field{margin-bottom:8px}' +
            '.guardpro-mobile-eid-field label{display:block;font-size:12px;color:#555;margin-bottom:2px}' +
            '.guardpro-mobile-eid-field input,.guardpro-mobile-eid-field select{width:100%;padding:6px 8px;box-sizing:border-box}' +
            '.guardpro-mobile-eid-warn{color:#856404;background:#fff3cd;padding:8px;border-radius:6px;font-size:13px;margin:8px 0}' +
            '@media (max-width:480px){.guardpro-mobile-eid-modal{width:96%;height:94vh;padding:10px}.guardpro-mobile-eid-modal video{max-height:44vh}.guardpro-mobile-eid-actions button{min-width:130px}}';
        document.head.appendChild(style);
    }

    function mkBtn(label, cls) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = label;
        if (cls) {
            b.className = cls;
        }
        return b;
    }

    /** Call from a click/tap handler so mobile browsers show the camera permission prompt. */
    function requestCameraWithFallbacks() {
        if (typeof window.isSecureContext !== 'undefined' && window.isSecureContext === false) {
            return Promise.reject(
                new Error('Camera needs a secure HTTPS connection. Open the site with https://')
            );
        }
        try {
            if (
                window.MobilePushToTalk &&
                typeof window.MobilePushToTalk.releaseMicrophoneForCamera === 'function'
            ) {
                window.MobilePushToTalk.releaseMicrophoneForCamera();
            }
        } catch (e) {
            console.debug('[GuardPro Mobile EID] PTT mic release skipped', e);
        }
        var md = navigator.mediaDevices;
        if (!md || typeof md.getUserMedia !== 'function') {
            return Promise.reject(new Error('Camera is not available in this browser.'));
        }
        var hi = {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
        };
        var attempts = [
            { video: hi, audio: false },
            { video: { facingMode: 'environment' }, audio: false },
            { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
        ];
        var i = 0;
        function tryNext(err) {
            if (i >= attempts.length) {
                return Promise.reject(err || new Error('Could not open the camera.'));
            }
            var constraints = attempts[i++];
            return md.getUserMedia(constraints).catch(tryNext);
        }
        return tryNext();
    }

    function openScanWizard(formRoot, initialStream) {
        injectStyles();
        var overlay = document.createElement('div');
        overlay.className = 'guardpro-mobile-eid-overlay';
        var modal = document.createElement('div');
        modal.className = 'guardpro-mobile-eid-modal';

        var step = 'front';
        var stream = initialStream || null;
        var frontOcrDataUrl = '';
        var backOcrDataUrl = '';
        var frontPhotoDataUrl = '';
        var reviewData = null;

        var title = document.createElement('h3');
        var sub = document.createElement('p');
        sub.className = 'guardpro-mobile-eid-sub';

        var video = document.createElement('video');
        video.setAttribute('playsinline', 'true');
        video.setAttribute('webkit-playsinline', 'true');
        video.setAttribute('autoplay', 'true');
        video.muted = true;
        var cameraWrap = document.createElement('div');
        cameraWrap.className = 'guardpro-mobile-eid-camera-wrap';
        var guide = document.createElement('div');
        guide.className = 'guardpro-mobile-eid-guide';
        ['tl', 'tr', 'bl', 'br'].forEach(function (pos) {
            var c = document.createElement('span');
            c.className = 'corner ' + pos;
            guide.appendChild(c);
        });
        cameraWrap.appendChild(video);
        cameraWrap.appendChild(guide);

        var previewWrap = document.createElement('div');
        previewWrap.className = 'preview';
        previewWrap.style.display = 'none';

        var reviewForm = document.createElement('div');
        reviewForm.style.display = 'none';
        var bodyWrap = document.createElement('div');
        bodyWrap.className = 'guardpro-mobile-eid-body';

        var actions = document.createElement('div');
        actions.className = 'guardpro-mobile-eid-actions';

        function stopCamera() {
            if (stream) {
                stream.getTracks().forEach(function (t) {
                    t.enabled = false;
                    t.stop();
                });
                stream = null;
            }
            try {
                video.pause();
            } catch (e) {}
            video.srcObject = null;
            video.removeAttribute('src');
        }

        function closeAll() {
            stopCamera();
            overlay.remove();
            try {
                if (
                    window.MobilePushToTalk &&
                    typeof window.MobilePushToTalk.resumeMicrophoneAfterCamera === 'function'
                ) {
                    window.MobilePushToTalk.resumeMicrophoneAfterCamera();
                }
            } catch (e) {
                console.debug('[GuardPro Mobile EID] PTT mic resume skipped', e);
            }
        }

        function streamHasLiveVideoTrack() {
            if (!stream || !stream.getTracks) {
                return false;
            }
            var tracks = stream.getTracks();
            for (var ti = 0; ti < tracks.length; ti++) {
                if (tracks[ti].kind === 'video' && tracks[ti].readyState === 'live') {
                    return true;
                }
            }
            return false;
        }

        function attachStreamToVideo() {
            video.srcObject = stream;
            try {
                var tracks = stream && stream.getVideoTracks ? stream.getVideoTracks() : [];
                if (tracks && tracks[0] && typeof tracks[0].applyConstraints === 'function') {
                    tracks[0].applyConstraints({
                        advanced: [{ focusMode: 'continuous' }, { exposureMode: 'continuous' }],
                    }).catch(function () {});
                }
            } catch (e) {
                console.debug('[GuardPro Mobile EID] applyConstraints skipped', e);
            }
            var p = video.play && video.play();
            if (p && typeof p.catch === 'function') {
                p.catch(function () {});
            }
        }

        /**
         * Start or reuse camera. Call requestCameraWithFallbacks from a tap handler before
         * opening the wizard when possible; later steps (retake, back side) run from taps too.
         */
        function startCamera() {
            previewWrap.style.display = 'none';
            reviewForm.style.display = 'none';
            cameraWrap.style.display = 'block';
            video.style.display = 'block';
            if (streamHasLiveVideoTrack()) {
                attachStreamToVideo();
                return;
            }
            stopCamera();
            if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
                alert('Camera is not available in this browser.');
                closeAll();
                return;
            }
            requestCameraWithFallbacks()
                .then(function (s) {
                    stream = s;
                    attachStreamToVideo();
                })
                .catch(function (e) {
                    console.error(e);
                    var msg = (e && e.name) || (e && e.message) || String(e);
                    var hint =
                        'Use HTTPS, tap the button again, and choose Allow when the browser asks for camera access. ' +
                        'If you denied it before, open the site settings for this app and enable the camera.';
                    if (
                        msg === 'NotAllowedError' ||
                        (e && e.message && String(e.message).toLowerCase().indexOf('denied') !== -1)
                    ) {
                        alert('Camera permission is required.\n\n' + hint);
                    } else {
                        alert('Could not open the camera (' + msg + ').\n\n' + hint);
                    }
                    closeAll();
                });
        }

        /**
         * Map the on-screen guide rect to intrinsic video pixels for object-fit: cover.
         * scale = max(cw/iw, ch/ih); offsets center the scaled frame in the element.
         */
        function clientGuideToIntrinsicCrop(guideRect) {
            var iw = video.videoWidth || 1280;
            var ih = video.videoHeight || 720;
            var vrect = video.getBoundingClientRect();
            var cw = vrect.width || video.clientWidth || 1;
            var ch = vrect.height || video.clientHeight || 1;
            if (!iw || !ih) {
                return { cropX: 0, cropY: 0, cropW: iw, cropH: ih };
            }
            var scale = Math.max(cw / iw, ch / ih);
            var ox = (cw - iw * scale) / 2;
            var oy = (ch - ih * scale) / 2;
            var gl = guideRect.left - vrect.left;
            var gt = guideRect.top - vrect.top;
            var gw = guideRect.width;
            var gh = guideRect.height;
            var ix0 = (gl - ox) / scale;
            var iy0 = (gt - oy) / scale;
            var ix1 = (gl + gw - ox) / scale;
            var iy1 = (gt + gh - oy) / scale;
            var cropX = Math.max(0, Math.min(iw - 1, Math.floor(Math.min(ix0, ix1))));
            var cropY = Math.max(0, Math.min(ih - 1, Math.floor(Math.min(iy0, iy1))));
            var cropW = Math.min(iw - cropX, Math.max(1, Math.ceil(Math.max(ix0, ix1) - cropX)));
            var cropH = Math.min(ih - cropY, Math.max(1, Math.ceil(Math.max(iy0, iy1) - cropY)));
            return { cropX: cropX, cropY: cropY, cropW: cropW, cropH: cropH };
        }

        /**
         * Returns { ocr: dataUrl, photo: dataUrl } — same card crop; photo is color for id_photo,
         * ocr is contrast-boosted grayscale for the server.
         */
        function captureCardImages() {
            var srcW = video.videoWidth || 1280;
            var srcH = video.videoHeight || 720;
            var sourceCanvas = document.createElement('canvas');
            sourceCanvas.width = srcW;
            sourceCanvas.height = srcH;
            var sourceCtx = sourceCanvas.getContext('2d');
            sourceCtx.drawImage(video, 0, 0, srcW, srcH);

            var crop = clientGuideToIntrinsicCrop(guide.getBoundingClientRect());
            if (crop.cropW < 120 || crop.cropH < 80) {
                crop = { cropX: 0, cropY: 0, cropW: srcW, cropH: srcH };
            }

            var maxWidth = 2000;
            var outW = Math.min(maxWidth, crop.cropW);
            var outH = Math.max(1, Math.round((crop.cropH * outW) / crop.cropW));

            var colorOut = document.createElement('canvas');
            colorOut.width = outW;
            colorOut.height = outH;
            var cctx = colorOut.getContext('2d');
            cctx.drawImage(
                sourceCanvas,
                crop.cropX,
                crop.cropY,
                crop.cropW,
                crop.cropH,
                0,
                0,
                outW,
                outH
            );
            var photoDataUrl = colorOut.toDataURL('image/jpeg', 0.92);

            var ocrOut = document.createElement('canvas');
            ocrOut.width = outW;
            ocrOut.height = outH;
            var octx = ocrOut.getContext('2d', { willReadFrequently: true });
            octx.drawImage(colorOut, 0, 0);
            try {
                var img = octx.getImageData(0, 0, outW, outH);
                var d = img.data;
                for (var i = 0; i < d.length; i += 4) {
                    var y = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
                    var v = (y - 128) * 1.25 + 128;
                    if (v < 0) v = 0;
                    if (v > 255) v = 255;
                    d[i] = v;
                    d[i + 1] = v;
                    d[i + 2] = v;
                }
                octx.putImageData(img, 0, 0);
            } catch (e) {
                console.debug('[GuardPro Mobile EID] OCR enhancement skipped', e);
            }
            var ocrDataUrl = ocrOut.toDataURL('image/jpeg', 0.92);

            return { ocr: ocrDataUrl, photo: photoDataUrl };
        }

        function showPreview(dataUrl) {
            cameraWrap.style.display = 'none';
            previewWrap.style.display = 'block';
            previewWrap.innerHTML = '';
            var img = document.createElement('img');
            img.src = dataUrl;
            img.alt = 'capture';
            previewWrap.appendChild(img);
        }

        function clearActions() {
            actions.innerHTML = '';
        }

        function renderCaptureStep() {
            clearActions();
            reviewForm.style.display = 'none';
            previewWrap.style.display = 'none';
            cameraWrap.style.display = 'block';
            video.style.display = 'block';

            if (step === 'front') {
                title.textContent = 'Scan Emirates ID — Front';
                sub.textContent = 'Position the front of the card in the frame, then capture.';
            } else {
                title.textContent = 'Scan Emirates ID — Back';
                sub.textContent = 'Flip the card. Capture the back (MRZ helps accuracy).';
            }

            var btnCap = mkBtn(step === 'front' ? 'Capture front' : 'Capture back', 'primary');
            var btnCancel = mkBtn('Cancel', 'danger');
            btnCancel.addEventListener('click', closeAll);
            btnCap.addEventListener('click', function () {
                var cap = captureCardImages();
                var previewUrl = cap.photo;
                var ocrUrl = cap.ocr;
                stopCamera();
                showPreview(previewUrl);
                clearActions();
                var btnRetake = mkBtn('Retake');
                var btnCont = mkBtn(step === 'front' ? 'Next: back' : 'Extract data', 'primary');
                btnRetake.addEventListener('click', function () {
                    renderCaptureStep();
                });
                btnCont.addEventListener('click', function () {
                    if (step === 'front') {
                        frontOcrDataUrl = ocrUrl;
                        frontPhotoDataUrl = cap.photo;
                        step = 'back';
                        renderCaptureStep();
                        startCamera();
                    } else {
                        backOcrDataUrl = ocrUrl;
                        runExtract();
                    }
                });
                actions.appendChild(btnRetake);
                actions.appendChild(btnCont);
            });
            actions.appendChild(btnCap);
            actions.appendChild(btnCancel);
            startCamera();
        }

        function runExtract() {
            stopCamera();
            previewWrap.style.display = 'none';
            cameraWrap.style.display = 'none';
            clearActions();
            title.textContent = 'Extracting…';
            sub.textContent = 'Reading text from images. Please wait.';

            var frontB64 = frontOcrDataUrl ? dataUrlToRawB64(frontOcrDataUrl) : '';
            var backB64 = backOcrDataUrl ? dataUrlToRawB64(backOcrDataUrl) : '';

            jsonRpc(OCR_URL, {
                front_image: frontB64 || null,
                back_image: backB64 || null,
            })
                .then(function (result) {
                    if (!result.success) {
                        alert(result.error || 'OCR failed.');
                        closeAll();
                        return;
                    }
                    reviewData = result;
                    showReviewForm();
                })
                .catch(function (e) {
                    console.error(e);
                    alert('OCR request failed: ' + (e.message || String(e)));
                    closeAll();
                });
        }

        function showReviewForm() {
            title.textContent = 'Review extracted data';
            sub.textContent = 'Correct any mistakes, then apply to the form.';
            reviewForm.style.display = 'block';
            reviewForm.innerHTML = '';

            if (reviewData.warnings && reviewData.warnings.length) {
                var w = document.createElement('div');
                w.className = 'guardpro-mobile-eid-warn';
                w.textContent = reviewData.warnings.join(' ');
                reviewForm.appendChild(w);
            }

            var fieldSpec = [
                ['name', 'Visitor name (English)', 'text'],
                ['id_number', 'Emirates ID number', 'text'],
                ['nationality', 'Nationality', 'text'],
                ['date_of_birth', 'Date of birth', 'date'],
                ['gender', 'Gender', 'select', ['', 'male', 'female']],
                ['id_expiry_date', 'ID expiry', 'date'],
                ['id_issue_date', 'ID issue', 'date'],
                ['occupation', 'Occupation', 'text'],
                ['employer_name', 'Employer', 'text'],
                ['issuing_place', 'Issuing place', 'text'],
            ];

            var genderLabels = { '': '—', male: 'Male', female: 'Female' };

            for (var fi = 0; fi < fieldSpec.length; fi++) {
                var spec = fieldSpec[fi];
                var fname = spec[0];
                var flabel = spec[1];
                var ftype = spec[2];
                var wrap = document.createElement('div');
                wrap.className = 'guardpro-mobile-eid-field';
                var lab = document.createElement('label');
                lab.textContent = flabel;
                wrap.appendChild(lab);
                var input;
                if (ftype === 'select') {
                    input = document.createElement('select');
                    var opts = spec[3];
                    for (var oi = 0; oi < opts.length; oi++) {
                        var ov = opts[oi];
                        var o = document.createElement('option');
                        o.value = ov;
                        o.textContent = genderLabels[ov] || ov;
                        input.appendChild(o);
                    }
                } else {
                    input = document.createElement('input');
                    input.type = ftype;
                }
                input.dataset.field = fname;
                input.value =
                    reviewData[fname] !== undefined && reviewData[fname] !== null
                        ? String(reviewData[fname])
                        : '';
                wrap.appendChild(input);
                reviewForm.appendChild(wrap);
            }

            clearActions();
            var btnApply = mkBtn('Apply to form', 'primary');
            var btnClose = mkBtn('Close');
            btnClose.addEventListener('click', closeAll);
            btnApply.addEventListener('click', function () {
                var fields = reviewForm.querySelectorAll('[data-field]');
                for (var i = 0; i < fields.length; i++) {
                    var inp = fields[i];
                    setFormField(formRoot, inp.dataset.field, inp.value);
                }
                if (frontPhotoDataUrl) {
                    setIdPhotoHidden(formRoot, dataUrlToRawB64(frontPhotoDataUrl));
                }
                var idType = formRoot.querySelector('[name="id_type"]');
                if (idType) {
                    idType.value = 'emirates_id';
                    idType.dispatchEvent(new Event('change', { bubbles: true }));
                }
                alert('Fields updated from scan. Review and submit the form.');
                closeAll();
            });
            actions.appendChild(btnApply);
            actions.appendChild(btnClose);
        }

        bodyWrap.appendChild(cameraWrap);
        bodyWrap.appendChild(previewWrap);
        bodyWrap.appendChild(reviewForm);
        modal.appendChild(title);
        modal.appendChild(sub);
        modal.appendChild(bodyWrap);
        modal.appendChild(actions);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        if (stream && streamHasLiveVideoTrack()) {
            video.srcObject = stream;
            attachStreamToVideo();
        }

        renderCaptureStep();
    }

    function cameraErrorAlert(e) {
        console.error('[GuardPro Mobile EID] Camera error', e);
        var name = e && e.name;
        var hint =
            'When the browser asks, tap Allow. On Android: Chrome menu → Settings → Site settings → Camera, or App info → Permissions for Chrome. Installed PWAs use the browser permission, not a separate app camera toggle.';
        if (name === 'NotAllowedError') {
            alert('Camera access was blocked.\n\n' + hint);
        } else if (name === 'NotFoundError') {
            alert('No camera was found on this device.');
        } else {
            var detail = e && e.message ? e.message : 'Could not open the camera.';
            alert(detail + '\n\n' + hint);
        }
    }

    function startEidScanPipeline(btn) {
        var form = btn.closest('form') || document.body;
        console.log('[GuardPro Mobile EID] Scan started');
        requestCameraWithFallbacks()
            .then(function (s) {
                openScanWizard(form, s);
            })
            .catch(cameraErrorAlert);
    }

    var __eidLastTapMs = 0;
    window.__guardproEidRunScan = function (ev, el) {
        var now = Date.now();
        if (now - __eidLastTapMs < 900) {
            return false;
        }
        __eidLastTapMs = now;
        var btn = el;
        if (!btn && ev && ev.target && typeof ev.target.closest === 'function') {
            btn = ev.target.closest('[data-guardpro-eid-scan]');
        }
        if (!btn || !document.body || !document.body.contains(btn)) {
            return false;
        }
        startEidScanPipeline(btn);
        return false;
    };

    function handleDelegatedEidScanPointerOrClick(ev) {
        if (ev.type === 'pointerdown' && ev.pointerType !== 'touch') {
            return;
        }
        var el = ev.target;
        if (!el || typeof el.closest !== 'function') {
            return;
        }
        var btn = el.closest('[data-guardpro-eid-scan]');
        if (!btn || !document.body || !document.body.contains(btn)) {
            return;
        }
        window.guardproEidTriggerScan(ev, btn);
    }

    document.addEventListener('pointerdown', handleDelegatedEidScanPointerOrClick, true);
    document.addEventListener('click', handleDelegatedEidScanPointerOrClick, true);

    function bindScanButtons() {
        console.log('[GuardPro Mobile EID] Delegation + inline onclick active');
    }

    window.GuardProMobileEmiratesIdScan = {
        open: openScanWizard,
        bind: bindScanButtons,
        requestCamera: requestCameraWithFallbacks,
    };
})();
