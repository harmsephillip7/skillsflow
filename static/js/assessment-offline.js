/**
 * SkillsFlow Assessment Offline Sync Module
 * Handles IndexedDB storage and sync for offline assessment capture
 */

class AssessmentOfflineStore {
    constructor() {
        this.dbName = 'skillsflow_assessments';
        this.dbVersion = 1;
        this.db = null;
    }

    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('IndexedDB error:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('IndexedDB initialized');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Store for pending assessment results
                if (!db.objectStoreNames.contains('pending_results')) {
                    const resultsStore = db.createObjectStore('pending_results', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    resultsStore.createIndex('enrollment_id', 'enrollment_id', { unique: false });
                    resultsStore.createIndex('schedule_id', 'schedule_id', { unique: false });
                    resultsStore.createIndex('synced', 'synced', { unique: false });
                }

                // Store for pending evidence uploads
                if (!db.objectStoreNames.contains('pending_evidence')) {
                    const evidenceStore = db.createObjectStore('pending_evidence', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    evidenceStore.createIndex('result_id', 'result_id', { unique: false });
                    evidenceStore.createIndex('synced', 'synced', { unique: false });
                }

                // Store for cached schedule data
                if (!db.objectStoreNames.contains('schedules')) {
                    const scheduleStore = db.createObjectStore('schedules', {
                        keyPath: 'id'
                    });
                    scheduleStore.createIndex('date', 'scheduled_date', { unique: false });
                }

                // Store for signatures
                if (!db.objectStoreNames.contains('signatures')) {
                    const sigStore = db.createObjectStore('signatures', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    sigStore.createIndex('schedule_id', 'schedule_id', { unique: false });
                }
            };
        });
    }

    // Save a pending assessment result
    async saveResult(result) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_results'], 'readwrite');
            const store = transaction.objectStore('pending_results');

            const data = {
                ...result,
                synced: false,
                created_at: new Date().toISOString()
            };

            const request = store.add(data);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Get all unsynced results
    async getUnsyncedResults() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_results'], 'readonly');
            const store = transaction.objectStore('pending_results');
            const index = store.index('synced');
            const request = index.getAll(IDBKeyRange.only(false));

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Mark result as synced
    async markResultSynced(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_results'], 'readwrite');
            const store = transaction.objectStore('pending_results');
            
            const getRequest = store.get(id);
            getRequest.onsuccess = () => {
                const data = getRequest.result;
                if (data) {
                    data.synced = true;
                    data.synced_at = new Date().toISOString();
                    const putRequest = store.put(data);
                    putRequest.onsuccess = () => resolve();
                    putRequest.onerror = () => reject(putRequest.error);
                } else {
                    resolve();
                }
            };
            getRequest.onerror = () => reject(getRequest.error);
        });
    }

    // Save evidence (base64 image)
    async saveEvidence(evidence) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_evidence'], 'readwrite');
            const store = transaction.objectStore('pending_evidence');

            const data = {
                ...evidence,
                synced: false,
                created_at: new Date().toISOString()
            };

            const request = store.add(data);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Get evidence for a result
    async getEvidenceForResult(resultId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_evidence'], 'readonly');
            const store = transaction.objectStore('pending_evidence');
            const index = store.index('result_id');
            const request = index.getAll(IDBKeyRange.only(resultId));

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Get all unsynced evidence
    async getUnsyncedEvidence() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_evidence'], 'readonly');
            const store = transaction.objectStore('pending_evidence');
            const index = store.index('synced');
            const request = index.getAll(IDBKeyRange.only(false));

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Mark evidence as synced
    async markEvidenceSynced(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_evidence'], 'readwrite');
            const store = transaction.objectStore('pending_evidence');
            
            const getRequest = store.get(id);
            getRequest.onsuccess = () => {
                const data = getRequest.result;
                if (data) {
                    data.synced = true;
                    const putRequest = store.put(data);
                    putRequest.onsuccess = () => resolve();
                    putRequest.onerror = () => reject(putRequest.error);
                } else {
                    resolve();
                }
            };
            getRequest.onerror = () => reject(getRequest.error);
        });
    }

    // Cache schedule data for offline use
    async cacheSchedule(schedule) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['schedules'], 'readwrite');
            const store = transaction.objectStore('schedules');
            const request = store.put(schedule);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    // Get cached schedule
    async getCachedSchedule(scheduleId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['schedules'], 'readonly');
            const store = transaction.objectStore('schedules');
            const request = store.get(scheduleId);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Get results for a schedule
    async getResultsForSchedule(scheduleId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_results'], 'readonly');
            const store = transaction.objectStore('pending_results');
            const index = store.index('schedule_id');
            const request = index.getAll(IDBKeyRange.only(scheduleId));

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Clear synced results (cleanup)
    async clearSyncedResults() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pending_results'], 'readwrite');
            const store = transaction.objectStore('pending_results');
            const index = store.index('synced');
            const request = index.openCursor(IDBKeyRange.only(true));

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    cursor.delete();
                    cursor.continue();
                } else {
                    resolve();
                }
            };
            request.onerror = () => reject(request.error);
        });
    }

    // Get pending count
    async getPendingCount() {
        const unsynced = await this.getUnsyncedResults();
        return unsynced.length;
    }
}

/**
 * Assessment Sync Manager
 * Handles synchronization between local IndexedDB and server
 */
class AssessmentSyncManager {
    constructor(store, csrfToken) {
        this.store = store;
        this.csrfToken = csrfToken;
        this.isSyncing = false;
        this.syncCallbacks = [];
    }

    onSyncStatus(callback) {
        this.syncCallbacks.push(callback);
    }

    notifyStatus(status, message) {
        this.syncCallbacks.forEach(cb => cb(status, message));
    }

    // Quick save a single result (called after each assessment)
    async quickSave(scheduleId, enrollmentId, activityId, result, comments) {
        // Save to IndexedDB first
        const localResult = {
            schedule_id: scheduleId,
            enrollment_id: enrollmentId,
            activity_id: activityId,
            result: result,
            comments: comments,
            client_timestamp: new Date().toISOString()
        };

        const localId = await this.store.saveResult(localResult);

        // Try to sync immediately if online
        if (navigator.onLine) {
            try {
                await this.syncSingleResult(localId, localResult);
            } catch (error) {
                console.log('Quick save failed, will retry later:', error);
            }
        }

        return localId;
    }

    // Sync a single result to server
    async syncSingleResult(localId, result) {
        const response = await fetch('/assessments/api/quick-save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(result)
        });

        if (response.ok) {
            await this.store.markResultSynced(localId);
            return true;
        }
        
        throw new Error('Sync failed');
    }

    // Bulk sync all pending results
    async syncAll() {
        if (this.isSyncing) return;
        if (!navigator.onLine) {
            this.notifyStatus('offline', 'No connection');
            return;
        }

        this.isSyncing = true;
        this.notifyStatus('syncing', 'Syncing...');

        try {
            const pendingResults = await this.store.getUnsyncedResults();
            
            if (pendingResults.length === 0) {
                this.notifyStatus('success', 'All synced');
                return;
            }

            const response = await fetch('/assessments/api/bulk-sync/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ results: pendingResults })
            });

            if (response.ok) {
                const data = await response.json();
                
                // Mark synced results
                for (const result of pendingResults) {
                    await this.store.markResultSynced(result.id);
                }

                this.notifyStatus('success', `${pendingResults.length} synced`);

                // Handle any conflicts
                if (data.conflicts && data.conflicts.length > 0) {
                    console.log('Sync conflicts:', data.conflicts);
                    // Client wins by default, but log for audit
                }
            } else {
                throw new Error('Bulk sync failed');
            }
        } catch (error) {
            console.error('Sync error:', error);
            this.notifyStatus('error', 'Sync failed');
        } finally {
            this.isSyncing = false;
        }
    }

    // Upload pending evidence
    async syncEvidence() {
        if (!navigator.onLine) return;

        const pendingEvidence = await this.store.getUnsyncedEvidence();
        
        for (const evidence of pendingEvidence) {
            try {
                const response = await fetch('/assessments/api/evidence/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.csrfToken
                    },
                    body: JSON.stringify({
                        result_id: evidence.result_id,
                        image_data: evidence.image_data,
                        description: evidence.description
                    })
                });

                if (response.ok) {
                    await this.store.markEvidenceSynced(evidence.id);
                }
            } catch (error) {
                console.error('Evidence sync failed:', error);
            }
        }
    }

    // Register for background sync
    async registerBackgroundSync() {
        if ('serviceWorker' in navigator && 'sync' in window) {
            try {
                const registration = await navigator.serviceWorker.ready;
                await registration.sync.register('sync-assessments');
                console.log('Background sync registered');
            } catch (error) {
                console.log('Background sync not supported:', error);
            }
        }
    }
}

// Export for use in templates
window.AssessmentOfflineStore = AssessmentOfflineStore;
window.AssessmentSyncManager = AssessmentSyncManager;
