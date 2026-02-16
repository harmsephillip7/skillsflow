/**
 * SkillsFlow WBL Offline Support
 * Handles IndexedDB storage and sync for offline attendance capture
 */

class WBLOfflineManager {
    constructor() {
        this.dbName = 'SkillsFlowWBL';
        this.dbVersion = 1;
        this.db = null;
        this.isOnline = navigator.onLine;
        
        this.init();
    }
    
    async init() {
        // Initialize IndexedDB
        await this.openDatabase();
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/js/sw.js');
                console.log('Service Worker registered:', registration.scope);
            } catch (error) {
                console.error('Service Worker registration failed:', error);
            }
        }
        
        // Listen for online/offline events
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
        
        // Check for pending sync on load
        if (this.isOnline) {
            this.syncPendingData();
        }
        
        // Update UI indicator
        this.updateConnectionStatus();
    }
    
    openDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => {
                console.error('IndexedDB error:', request.error);
                reject(request.error);
            };
            
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Pending attendance records
                if (!db.objectStoreNames.contains('pendingAttendance')) {
                    const attendanceStore = db.createObjectStore('pendingAttendance', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    attendanceStore.createIndex('placement_id', 'placement_id', { unique: false });
                    attendanceStore.createIndex('date', 'date', { unique: false });
                    attendanceStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Pending logbook entries
                if (!db.objectStoreNames.contains('pendingLogbook')) {
                    const logbookStore = db.createObjectStore('pendingLogbook', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    logbookStore.createIndex('placement_id', 'placement_id', { unique: false });
                    logbookStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Cached placement data
                if (!db.objectStoreNames.contains('placementCache')) {
                    db.createObjectStore('placementCache', { keyPath: 'placement_id' });
                }
                
                // Cached learner list
                if (!db.objectStoreNames.contains('learnerCache')) {
                    db.createObjectStore('learnerCache', { keyPath: 'id' });
                }
            };
        });
    }
    
    handleOnline() {
        this.isOnline = true;
        this.updateConnectionStatus();
        this.syncPendingData();
        this.showNotification('Back online! Syncing data...', 'success');
    }
    
    handleOffline() {
        this.isOnline = false;
        this.updateConnectionStatus();
        this.showNotification('You are offline. Data will be saved locally.', 'warning');
    }
    
    updateConnectionStatus() {
        const indicator = document.getElementById('connectionStatus');
        if (indicator) {
            if (this.isOnline) {
                indicator.innerHTML = '<i class="bi bi-wifi text-success"></i>';
                indicator.title = 'Online';
            } else {
                indicator.innerHTML = '<i class="bi bi-wifi-off text-danger"></i>';
                indicator.title = 'Offline - Data saved locally';
            }
        }
    }
    
    // Save attendance record (online or offline)
    async saveAttendance(data) {
        if (this.isOnline) {
            try {
                const response = await this.submitAttendanceOnline(data);
                return { success: true, online: true, data: response };
            } catch (error) {
                // Fall back to offline storage
                return this.saveAttendanceOffline(data);
            }
        } else {
            return this.saveAttendanceOffline(data);
        }
    }
    
    async submitAttendanceOnline(data) {
        const response = await fetch('/portals/mentor/attendance/submit/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error('Server error');
        }
        
        return response.json();
    }
    
    async saveAttendanceOffline(data) {
        const tx = this.db.transaction('pendingAttendance', 'readwrite');
        const store = tx.objectStore('pendingAttendance');
        
        const record = {
            ...data,
            timestamp: Date.now(),
            synced: false
        };
        
        await store.add(record);
        
        return { 
            success: true, 
            offline: true, 
            message: 'Saved offline. Will sync when connected.' 
        };
    }
    
    // Save logbook entry (online or offline)
    async saveLogbookEntry(data) {
        if (this.isOnline) {
            try {
                const response = await this.submitLogbookOnline(data);
                return { success: true, online: true, data: response };
            } catch (error) {
                return this.saveLogbookOffline(data);
            }
        } else {
            return this.saveLogbookOffline(data);
        }
    }
    
    async submitLogbookOnline(data) {
        const response = await fetch('/portals/mentor/logbook/submit/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error('Server error');
        }
        
        return response.json();
    }
    
    async saveLogbookOffline(data) {
        const tx = this.db.transaction('pendingLogbook', 'readwrite');
        const store = tx.objectStore('pendingLogbook');
        
        const record = {
            ...data,
            timestamp: Date.now(),
            synced: false
        };
        
        await store.add(record);
        
        return { 
            success: true, 
            offline: true, 
            message: 'Saved offline. Will sync when connected.' 
        };
    }
    
    // Get pending (unsynced) records count
    async getPendingCount() {
        const attendanceCount = await this.getStoreCount('pendingAttendance');
        const logbookCount = await this.getStoreCount('pendingLogbook');
        
        return {
            attendance: attendanceCount,
            logbook: logbookCount,
            total: attendanceCount + logbookCount
        };
    }
    
    getStoreCount(storeName) {
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const index = store.index('synced');
            const request = index.count(IDBKeyRange.only(false));
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    // Sync all pending data
    async syncPendingData() {
        if (!this.isOnline) return;
        
        // Sync attendance
        await this.syncStore('pendingAttendance', '/portals/mentor/attendance/submit/');
        
        // Sync logbook entries
        await this.syncStore('pendingLogbook', '/portals/mentor/logbook/submit/');
        
        // Update pending count display
        const pending = await this.getPendingCount();
        if (pending.total === 0) {
            this.showNotification('All data synced successfully!', 'success');
        }
    }
    
    async syncStore(storeName, endpoint) {
        const tx = this.db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        const index = store.index('synced');
        
        const request = index.getAll(IDBKeyRange.only(false));
        
        request.onsuccess = async () => {
            const records = request.result;
            
            for (const record of records) {
                try {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCSRFToken()
                        },
                        body: JSON.stringify(record)
                    });
                    
                    if (response.ok) {
                        // Delete synced record
                        const deleteTx = this.db.transaction(storeName, 'readwrite');
                        const deleteStore = deleteTx.objectStore(storeName);
                        await deleteStore.delete(record.id);
                    }
                } catch (error) {
                    console.error('Sync failed for record:', record.id, error);
                }
            }
        };
    }
    
    // Cache placement data for offline use
    async cachePlacementData(placement) {
        const tx = this.db.transaction('placementCache', 'readwrite');
        const store = tx.objectStore('placementCache');
        
        await store.put({
            placement_id: placement.id,
            data: placement,
            cached_at: Date.now()
        });
    }
    
    // Get cached placement data
    async getCachedPlacement(placementId) {
        const tx = this.db.transaction('placementCache', 'readonly');
        const store = tx.objectStore('placementCache');
        
        return new Promise((resolve, reject) => {
            const request = store.get(placementId);
            request.onsuccess = () => resolve(request.result?.data);
            request.onerror = () => reject(request.error);
        });
    }
    
    // Cache learner list for offline use
    async cacheLearners(learners) {
        const tx = this.db.transaction('learnerCache', 'readwrite');
        const store = tx.objectStore('learnerCache');
        
        for (const learner of learners) {
            await store.put({
                id: learner.id,
                data: learner,
                cached_at: Date.now()
            });
        }
    }
    
    // Get cached learners
    async getCachedLearners() {
        const tx = this.db.transaction('learnerCache', 'readonly');
        const store = tx.objectStore('learnerCache');
        
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result.map(r => r.data));
            request.onerror = () => reject(request.error);
        });
    }
    
    // Utility: Get CSRF token
    getCSRFToken() {
        const cookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }
    
    // Utility: Show notification
    showNotification(message, type = 'info') {
        const container = document.getElementById('notifications') || document.body;
        
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        container.appendChild(notification);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Initialize on page load
let offlineManager;
document.addEventListener('DOMContentLoaded', () => {
    offlineManager = new WBLOfflineManager();
    
    // Expose for use in forms
    window.WBLOffline = offlineManager;
});

// Attendance Form Handler
function initAttendanceForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Saving...';
        submitBtn.disabled = true;
        
        try {
            const result = await offlineManager.saveAttendance(data);
            
            if (result.success) {
                if (result.offline) {
                    offlineManager.showNotification(result.message, 'warning');
                } else {
                    offlineManager.showNotification('Attendance saved successfully!', 'success');
                }
                form.reset();
            }
        } catch (error) {
            offlineManager.showNotification('Error saving attendance. Please try again.', 'danger');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

// Logbook Form Handler
function initLogbookForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Saving...';
        submitBtn.disabled = true;
        
        try {
            const result = await offlineManager.saveLogbookEntry(data);
            
            if (result.success) {
                if (result.offline) {
                    offlineManager.showNotification(result.message, 'warning');
                } else {
                    offlineManager.showNotification('Logbook entry saved successfully!', 'success');
                }
            }
        } catch (error) {
            offlineManager.showNotification('Error saving entry. Please try again.', 'danger');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

// Sync indicator component
function renderSyncIndicator(containerId) {
    const container = document.getElementById(containerId);
    if (!container || !offlineManager) return;
    
    offlineManager.getPendingCount().then(pending => {
        if (pending.total > 0) {
            container.innerHTML = `
                <div class="alert alert-warning d-flex align-items-center" role="alert">
                    <i class="bi bi-cloud-arrow-up me-2"></i>
                    <div>
                        <strong>${pending.total} record(s) pending sync</strong>
                        <button class="btn btn-sm btn-warning ms-3" onclick="offlineManager.syncPendingData()">
                            Sync Now
                        </button>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = '';
        }
    });
}
