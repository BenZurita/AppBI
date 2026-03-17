// =========================================================================
// DETECCIÓN AUTOMÁTICA DE ENTORNO
// =========================================================================

const hostname = window.location.hostname;
const port = window.location.port;

// Detectar tipo de entorno
const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
const isIPLocal = hostname.startsWith('192.168.') || 
                  hostname.startsWith('10.') || 
                  hostname.startsWith('172.16.');
const isNgrok = hostname.includes('ngrok') || hostname.includes('ngrok-free');
const isGitHubCodespace = hostname.includes('github.dev');

// URL base según el entorno
let API_BASE_URL;

if (isLocalhost) {
    // Misma PC: localhost
    API_BASE_URL = 'http://localhost:5000/api';
} else if (isIPLocal || isNgrok || isGitHubCodespace) {
    // Misma red (192.168.x.x) o túneles: usar el mismo hostname que el frontend
    API_BASE_URL = `${window.location.protocol}//${hostname}:${port || 5000}/api`;
} else {
    // Producción: mismo origen
    API_BASE_URL = `${window.location.origin}/api`;
}

console.log('[DEBUG] Hostname:', hostname);
console.log('[DEBUG] isLocalhost:', isLocalhost);
console.log('[DEBUG] isIPLocal:', isIPLocal);
console.log('[DEBUG] API_BASE_URL:', API_BASE_URL);

const apiService = {

    // =========================================================================
    // AUTENTICACIÓN
    // =========================================================================

    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        console.log('[LOGIN] Enviando a:', `${API_BASE_URL}/auth/token`);

        try {
            const response = await fetch(`${API_BASE_URL}/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
            });

            console.log('[LOGIN] Status:', response.status);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Error ${response.status}`);
            }

            const data = await response.json();
            console.log('[DEBUG] Login response:', data);

            localStorage.setItem('token', data.access_token);
            localStorage.setItem('username', data.username);
            localStorage.setItem('role', data.role);
            localStorage.setItem('can_view_all', data.can_view_all ? 'true' : 'false');
            
            if (data.hasOwnProperty('unified_team_sk')) {
                const valueToStore = data.unified_team_sk || '';
                localStorage.setItem('unified_team_sk', valueToStore);
                console.log('[DEBUG] Saved unified_team_sk:', valueToStore);
            } else {
                localStorage.removeItem('unified_team_sk');
                console.log('[DEBUG] No unified_team_sk key in response');
            }

            return data;

        } catch (error) {
            console.error('[LOGIN] Error:', error);
            throw error;
        }
    },

    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
        localStorage.removeItem('unified_team_sk');
        localStorage.removeItem('can_view_all');
        window.location.href = '/login.html';
    },

    getToken() {
        return localStorage.getItem('token');
    },

    getRole() {
        return localStorage.getItem('role') || 'restaurant';
    },

    canViewAll() {
        return localStorage.getItem('can_view_all') === 'true';
    },

    getUnifiedTeamSk() {
        const raw = localStorage.getItem('unified_team_sk');
        if (raw === null || raw === 'null' || raw === 'undefined' || raw === undefined) {
            return null;
        }
        return raw;
    },

    getUsername() {
        return localStorage.getItem('username') || 'Usuario';
    },

    isAdmin() {
        return this.getRole() === 'admin' || this.canViewAll();
    },

    isAuthenticated() {
        return !!this.getToken();
    },

    // =========================================================================
    // HELPER: fetch con token adjunto
    // =========================================================================

    async _fetch(url, options = {}) {
        const token = this.getToken();

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, { ...options, headers });

        if (response.status === 401) {
            this.logout();
            throw new Error('Sesión expirada o no autorizado');
        }

        if (response.status === 403) {
            throw new Error('No tienes permiso para ver estos datos');
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    // =========================================================================
    // DASHBOARD
    // =========================================================================

    async getDashboardData(dashboardType, params = {}) {
        try {
            const url = new URL(`${API_BASE_URL}/dashboard/${dashboardType}`);

            Object.entries(params).forEach(([key, value]) => {
                if (Array.isArray(value)) {
                    value.forEach(v => url.searchParams.append(key, v));
                } else if (value !== null && value !== undefined) {
                    url.searchParams.append(key, value);
                }
            });

            return await this._fetch(url.toString());
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            return this.getMockData(dashboardType);
        }
    },

    // =========================================================================
    // RESTAURANTES
    // =========================================================================

    async getRestaurants() {
        try {
            return await this._fetch(`${API_BASE_URL}/restaurants`);
        } catch (error) {
            console.error('Error fetching restaurants:', error);
            return { data: [] };
        }
    },

    // =========================================================================
    // ADMIN CACHE
    // =========================================================================

    async clearCache() {
        try {
            return await this._fetch(`${API_BASE_URL}/admin/cache/clear`, {
                method: 'POST',
            });
        } catch (error) {
            console.error('Error clearing cache:', error);
            return { success: false };
        }
    },

    // =========================================================================
    // MOCK DATA (fallback)
    // =========================================================================

    getMockData(type) {
        const mockData = {
            ventas: {
                kpis: [
                    { title: 'Ventas Totales', value: '$45,230', change: 12.5, trend: 'positive', icon: 'fas fa-dollar-sign', color: 'green' },
                    { title: 'Órdenes', value: '1,234', change: 8.2, trend: 'positive', icon: 'fas fa-shopping-bag', color: 'blue' },
                    { title: 'Ticket Promedio', value: '$36.65', change: -2.4, trend: 'negative', icon: 'fas fa-receipt', color: 'yellow' },
                    { title: 'Tasa Conversión', value: '3.2%', change: 0.8, trend: 'positive', icon: 'fas fa-percentage', color: 'red' }
                ],
                charts: []
            }
        };
        return mockData[type] || mockData.ventas;
    }
};