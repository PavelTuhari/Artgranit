/**
 * Barcode scanner using device camera.
 * Uses QuaggaJS CDN for decoding.
 * API: AgroBarcodeScanner.start(containerId, onDetected) / .stop()
 */
const AgroBarcodeScanner = (function() {
    'use strict';

    const QUAGGA_CDN = 'https://cdn.jsdelivr.net/npm/@ericblade/quagga2@1.8.4/dist/quagga.min.js';
    let _quaggaLoaded = false;
    let _running = false;
    let _onDetected = null;
    let _lastCode = '';
    let _lastTime = 0;

    function _loadQuagga() {
        return new Promise(function(resolve, reject) {
            if (_quaggaLoaded && window.Quagga) {
                resolve();
                return;
            }
            var s = document.createElement('script');
            s.src = QUAGGA_CDN;
            s.onload = function() { _quaggaLoaded = true; resolve(); };
            s.onerror = function() { reject(new Error('Failed to load QuaggaJS from CDN')); };
            document.head.appendChild(s);
        });
    }

    function _onProcessed(result) {
        var drawingCtx = Quagga.canvas.ctx.overlay;
        var drawingCanvas = Quagga.canvas.dom.overlay;
        if (!result) return;

        if (result.boxes) {
            drawingCtx.clearRect(0, 0,
                parseInt(drawingCanvas.getAttribute('width')),
                parseInt(drawingCanvas.getAttribute('height'))
            );
            result.boxes.filter(function(box) {
                return box !== result.box;
            }).forEach(function(box) {
                Quagga.ImageDebug.drawPath(box, { x: 0, y: 1 }, drawingCtx, { color: '#10b981', lineWidth: 2 });
            });
        }

        if (result.box) {
            Quagga.ImageDebug.drawPath(result.box, { x: 0, y: 1 }, drawingCtx, { color: '#059669', lineWidth: 3 });
        }

        if (result.codeResult && result.codeResult.code) {
            Quagga.ImageDebug.drawPath(result.line, { x: 'x', y: 'y' }, drawingCtx, { color: '#dc2626', lineWidth: 3 });
        }
    }

    function _onDetectedInternal(data) {
        var code = data.codeResult.code;
        var now = Date.now();

        // Debounce: ignore same code within 2 seconds
        if (code === _lastCode && (now - _lastTime) < 2000) return;
        _lastCode = code;
        _lastTime = now;

        if (typeof _onDetected === 'function') {
            _onDetected(code);
        }
    }

    /**
     * Start barcode scanner.
     * @param {string} containerId - DOM element ID to render camera into
     * @param {function} onDetected - callback(barcodeString)
     * @returns {Promise}
     */
    function start(containerId, onDetected) {
        _onDetected = onDetected;

        return _loadQuagga().then(function() {
            return new Promise(function(resolve, reject) {
                var container = document.getElementById(containerId);
                if (!container) {
                    reject(new Error('Container element not found: ' + containerId));
                    return;
                }

                Quagga.init({
                    inputStream: {
                        name: 'Live',
                        type: 'LiveStream',
                        target: container,
                        constraints: {
                            facingMode: 'environment',
                            width: { ideal: 1280 },
                            height: { ideal: 720 }
                        }
                    },
                    locator: {
                        patchSize: 'medium',
                        halfSample: true
                    },
                    numOfWorkers: navigator.hardwareConcurrency || 2,
                    decoder: {
                        readers: ['code_128_reader', 'ean_reader']
                    },
                    locate: true
                }, function(err) {
                    if (err) {
                        var msg = 'Camera error';
                        if (err.name === 'NotAllowedError' || (err.message && err.message.indexOf('Permission') >= 0)) {
                            msg = 'Camera permission denied. Please allow camera access and try again.';
                        } else if (err.name === 'NotFoundError') {
                            msg = 'No camera found on this device.';
                        } else if (err.name === 'NotReadableError') {
                            msg = 'Camera is in use by another application.';
                        }
                        reject(new Error(msg));
                        return;
                    }

                    Quagga.onProcessed(_onProcessed);
                    Quagga.onDetected(_onDetectedInternal);
                    Quagga.start();
                    _running = true;
                    resolve();
                });
            });
        });
    }

    /**
     * Stop the scanner and release camera.
     */
    function stop() {
        if (_running && window.Quagga) {
            Quagga.offProcessed(_onProcessed);
            Quagga.offDetected(_onDetectedInternal);
            Quagga.stop();
            _running = false;
        }
    }

    /**
     * Check if scanner is currently running.
     */
    function isRunning() {
        return _running;
    }

    return {
        start: start,
        stop: stop,
        isRunning: isRunning
    };
})();
