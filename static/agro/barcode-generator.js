/**
 * Barcode label generator for printing.
 * Uses JsBarcode CDN for rendering.
 * API: AgroBarcodeGenerator.generateLabels(barcodes, containerId)
 */
const AgroBarcodeGenerator = (function() {
    'use strict';

    const JSBARCODE_CDN = 'https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js';
    let _loaded = false;

    function _loadJsBarcode() {
        return new Promise(function(resolve, reject) {
            if (_loaded && window.JsBarcode) {
                resolve();
                return;
            }
            var s = document.createElement('script');
            s.src = JSBARCODE_CDN;
            s.onload = function() { _loaded = true; resolve(); };
            s.onerror = function() { reject(new Error('Failed to load JsBarcode from CDN')); };
            document.head.appendChild(s);
        });
    }

    function _injectPrintCSS() {
        if (document.getElementById('agro-barcode-print-css')) return;
        var style = document.createElement('style');
        style.id = 'agro-barcode-print-css';
        style.textContent = [
            '@media print {',
            '  body * { visibility: hidden !important; }',
            '  .barcode-print-container, .barcode-print-container * { visibility: visible !important; }',
            '  .barcode-print-container {',
            '    position: fixed !important;',
            '    left: 0; top: 0;',
            '    width: 210mm; /* A4 width */',
            '    margin: 0; padding: 5mm;',
            '    z-index: 99999;',
            '  }',
            '  .barcode-page {',
            '    display: grid;',
            '    grid-template-columns: repeat(3, 1fr);',
            '    grid-template-rows: repeat(8, 1fr);',
            '    gap: 2mm;',
            '    width: 200mm;',
            '    height: 287mm; /* A4 height minus margins */',
            '    page-break-after: always;',
            '  }',
            '  .barcode-label {',
            '    display: flex;',
            '    flex-direction: column;',
            '    align-items: center;',
            '    justify-content: center;',
            '    border: 0.5px solid #ccc;',
            '    padding: 1mm;',
            '    overflow: hidden;',
            '  }',
            '  .barcode-label svg { max-width: 100%; height: auto; }',
            '  .barcode-label .barcode-text {',
            '    font-family: monospace;',
            '    font-size: 9pt;',
            '    margin-top: 1mm;',
            '    color: #000;',
            '  }',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    /**
     * Generate printable barcode labels.
     * @param {Array<{code: string, text?: string}>} barcodes - array of barcode objects
     * @param {string} containerId - DOM element ID to render labels into
     * @returns {Promise}
     */
    function generateLabels(barcodes, containerId) {
        return _loadJsBarcode().then(function() {
            _injectPrintCSS();

            var container = document.getElementById(containerId);
            if (!container) throw new Error('Container not found: ' + containerId);

            container.innerHTML = '';
            container.className = 'barcode-print-container';

            var LABELS_PER_PAGE = 24; // 3 columns x 8 rows
            var pageCount = Math.ceil(barcodes.length / LABELS_PER_PAGE);

            for (var p = 0; p < pageCount; p++) {
                var page = document.createElement('div');
                page.className = 'barcode-page';

                var startIdx = p * LABELS_PER_PAGE;
                var endIdx = Math.min(startIdx + LABELS_PER_PAGE, barcodes.length);

                for (var i = startIdx; i < endIdx; i++) {
                    var bc = barcodes[i];
                    var code = typeof bc === 'string' ? bc : bc.code;
                    var text = typeof bc === 'string' ? bc : (bc.text || bc.code);

                    var label = document.createElement('div');
                    label.className = 'barcode-label';

                    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    svg.setAttribute('class', 'barcode-svg');
                    label.appendChild(svg);

                    var textEl = document.createElement('div');
                    textEl.className = 'barcode-text';
                    textEl.textContent = text;
                    label.appendChild(textEl);

                    page.appendChild(label);

                    // Render barcode into SVG
                    try {
                        JsBarcode(svg, code, {
                            format: 'CODE128',
                            width: 1.5,
                            height: 40,
                            displayValue: false,
                            margin: 2
                        });
                    } catch (e) {
                        textEl.textContent = 'ERR: ' + code;
                        console.warn('JsBarcode error for code:', code, e);
                    }
                }

                // Fill remaining cells with empty labels
                for (var j = endIdx - startIdx; j < LABELS_PER_PAGE; j++) {
                    var empty = document.createElement('div');
                    empty.className = 'barcode-label';
                    page.appendChild(empty);
                }

                container.appendChild(page);
            }
        });
    }

    /**
     * Generate labels and trigger print dialog.
     * @param {Array} barcodes
     * @param {string} containerId
     * @returns {Promise}
     */
    function generateAndPrint(barcodes, containerId) {
        return generateLabels(barcodes, containerId).then(function() {
            setTimeout(function() { window.print(); }, 300);
        });
    }

    return {
        generateLabels: generateLabels,
        generateAndPrint: generateAndPrint
    };
})();
