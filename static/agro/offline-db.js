/**
 * AGRO Field — IndexedDB wrapper for offline data storage.
 * Stores: references, purchases, crates, sync_queue.
 */
(function(global) {
'use strict';

var DB_NAME = 'agro_field_db';
var DB_VERSION = 1;
var db = null;

function openDB() {
    return new Promise(function(resolve, reject) {
        if (db) { resolve(db); return; }
        var request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = function(e) {
            var d = e.target.result;
            if (!d.objectStoreNames.contains('references')) {
                d.createObjectStore('references', { keyPath: 'type' });
            }
            if (!d.objectStoreNames.contains('purchases')) {
                var ps = d.createObjectStore('purchases', { keyPath: 'client_id', autoIncrement: true });
                ps.createIndex('status', 'status', { unique: false });
            }
            if (!d.objectStoreNames.contains('crates')) {
                var cs = d.createObjectStore('crates', { keyPath: 'client_id', autoIncrement: true });
                cs.createIndex('barcode', 'barcode', { unique: false });
            }
            if (!d.objectStoreNames.contains('sync_queue')) {
                var sq = d.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true });
                sq.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };

        request.onsuccess = function(e) {
            db = e.target.result;
            resolve(db);
        };

        request.onerror = function(e) {
            reject(e.target.error);
        };
    });
}

/* Generic helpers */
function txStore(storeName, mode) {
    return db.transaction(storeName, mode).objectStore(storeName);
}

function promisifyRequest(req) {
    return new Promise(function(resolve, reject) {
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
    });
}

/* References — keyed by type (suppliers, items, etc.) */
function saveReferences(type, data) {
    return openDB().then(function() {
        var store = txStore('references', 'readwrite');
        return promisifyRequest(store.put({ type: type, data: data, updated_at: Date.now() }));
    });
}

function getReferences(type) {
    return openDB().then(function() {
        var store = txStore('references', 'readonly');
        return promisifyRequest(store.get(type)).then(function(rec) {
            return rec ? rec.data : [];
        });
    });
}

function saveAllReferences(refsObj) {
    return openDB().then(function() {
        var promises = [];
        Object.keys(refsObj).forEach(function(key) {
            promises.push(saveReferences(key, refsObj[key]));
        });
        return Promise.all(promises);
    });
}

/* Sync queue — queued POST/PUT operations for when back online */
function queueOperation(op) {
    return openDB().then(function() {
        var store = txStore('sync_queue', 'readwrite');
        var entry = {
            url: op.url,
            method: op.method,
            body: op.body,
            client_uuid: generateUUID(),
            timestamp: Date.now(),
            status: 'pending'
        };
        return promisifyRequest(store.add(entry)).then(function() {
            return entry;
        });
    });
}

function getQueue() {
    return openDB().then(function() {
        var store = txStore('sync_queue', 'readonly');
        return promisifyRequest(store.getAll());
    });
}

function removeFromQueue(id) {
    return openDB().then(function() {
        var store = txStore('sync_queue', 'readwrite');
        return promisifyRequest(store.delete(id));
    });
}

function clearQueue() {
    return openDB().then(function() {
        var store = txStore('sync_queue', 'readwrite');
        return promisifyRequest(store.clear());
    });
}

function getQueueCount() {
    return openDB().then(function() {
        var store = txStore('sync_queue', 'readonly');
        return promisifyRequest(store.count());
    });
}

/* Sync — replay queued operations */
function syncQueue() {
    return getQueue().then(function(items) {
        if (!items.length) return { synced: 0, failed: 0 };

        var synced = 0, failed = 0;
        var chain = Promise.resolve();

        items.forEach(function(item) {
            chain = chain.then(function() {
                return fetch(item.url, {
                    method: item.method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(item.body)
                }).then(function(resp) {
                    return resp.json().then(function(data) {
                        if (data.success) {
                            synced++;
                            return removeFromQueue(item.id);
                        } else {
                            failed++;
                        }
                    });
                }).catch(function() {
                    failed++;
                });
            });
        });

        return chain.then(function() {
            return { synced: synced, failed: failed, total: items.length };
        });
    });
}

/* UUID generator */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0;
        var v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/* Offline purchases — store locally */
function savePurchaseLocally(purchaseData) {
    return openDB().then(function() {
        var store = txStore('purchases', 'readwrite');
        purchaseData.status = 'offline';
        purchaseData.created_at = Date.now();
        return promisifyRequest(store.add(purchaseData));
    });
}

function getOfflinePurchases() {
    return openDB().then(function() {
        var store = txStore('purchases', 'readonly');
        return promisifyRequest(store.getAll());
    });
}

/* Public API */
global.AgroOfflineDB = {
    open: openDB,
    saveReferences: saveReferences,
    getReferences: getReferences,
    saveAllReferences: saveAllReferences,
    queueOperation: queueOperation,
    getQueue: getQueue,
    getQueueCount: getQueueCount,
    removeFromQueue: removeFromQueue,
    clearQueue: clearQueue,
    syncQueue: syncQueue,
    savePurchaseLocally: savePurchaseLocally,
    getOfflinePurchases: getOfflinePurchases,
    generateUUID: generateUUID
};

})(typeof window !== 'undefined' ? window : self);
