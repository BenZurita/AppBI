const { createApp } = Vue;

createApp({
    components: {
        'sidebar': Sidebar,
        'dashboard-grid': DashboardGrid
    },
    data() {
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        const startOfYear = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
        
        // Verificar autenticación al iniciar
        if (!apiService.isAuthenticated()) {
            window.location.href = '/login.html';
            return {};
        }
        
        return {
            currentDashboard: 'daily',
            sidebarOpen: true,
            loading: false,
            
            // Datos de usuario - ESTAS VARIABLES FALTABAN EN EL VIEJO app.js
            userRole: apiService.getRole(),
            userRestaurantCode: apiService.getRestaurantCode(),
            username: apiService.getUsername(),
            userRestaurantName: '',
            
            kpis: [],
            secondaryMetrics: [],
            charts: [],
            
            selectedDate: todayStr,
            datePreset: 'today',
            restaurants: [],
            selectedRestaurant: apiService.isAdmin() ? 'all' : apiService.getRestaurantCode(),
            
            tableStartDate: startOfYear,
            tableEndDate: todayStr,
            tableRestaurants: apiService.isAdmin() ? ['all'] : [apiService.getRestaurantCode()],
            showRestaurantDropdown: false,
            
            tableData: [],
            tableColumns: [
                { key: 'restaurant', label: 'Restaurante' },
                { key: 'gmv', label: 'GMV' },
                { key: 'trx', label: 'Transacciones' },
                { key: 'aov', label: 'AOV' },
                { key: 'barquilla', label: 'Barquilla %' },
                { key: 'queso', label: 'Queso %' },
                { key: 'agrandado', label: 'Agrandado %' },
                { key: 'cambio', label: 'Cambio Pz %' }
            ],
            
            currentDate: today.toLocaleDateString('es-ES', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            })
        };
    },
    computed: {
        dashboardTitle() {
            const titles = {
                'daily': 'Daily Sales',
                'restaurants': 'Detalle de Restaurantes',
                'inventario': 'Inventario',
                'finanzas': 'Finanzas'
            };
            return titles[this.currentDashboard] || 'Dashboard';
        },
        
        // ESTE COMPUTED FALTABA - isAdmin
        isAdmin() {
            return apiService.isAdmin();
        },
        
        maxDate() {
            return new Date().toISOString().split('T')[0];
        },
        
        displayDate() {
            if (this.datePreset === 'today') return 'Hoy';
            if (this.datePreset === 'yesterday') return 'Ayer';
            return this.formatDisplayDate(this.selectedDate);
        },
        
        tablePeriodLabel() {
            return `${this.formatDisplayDate(this.tableStartDate)} - ${this.formatDisplayDate(this.tableEndDate)}`;
        },
        
        isAllSelected() {
            return this.tableRestaurants.includes('all') || this.tableRestaurants.length === this.restaurants.length;
        },
        
        selectedRestaurantsText() {
            if (this.tableRestaurants.includes('all') || this.tableRestaurants.length === 0) {
                return 'Todos los restaurantes';
            }
            if (this.tableRestaurants.length === 1) {
                const rest = this.restaurants.find(r => r.id === this.tableRestaurants[0]);
                return rest ? rest.name : '1 seleccionado';
            }
            return `${this.tableRestaurants.length} restaurantes seleccionados`;
        }
    },
    mounted() {
        // Verificar autenticación
        if (!apiService.isAuthenticated()) {
            window.location.href = '/login.html';
            return;
        }
        
        // Si no es admin, forzar su restaurante
        if (!apiService.isAdmin()) {
            this.selectedRestaurant = apiService.getRestaurantCode();
            this.tableRestaurants = [apiService.getRestaurantCode()];
        }
        
        this.loadRestaurants();
        this.loadDashboardData();
        
        if (window.innerWidth <= 768) {
            this.sidebarOpen = false;
        }
        
        // Cerrar dropdown al hacer click fuera
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-dropdown')) {
                this.showRestaurantDropdown = false;
            }
        });
    },
    methods: {
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        // ESTE MÉTODO FALTABA - logout
        logout() {
            apiService.logout();
        },
        
        async changeDashboard(dashboardId) {
            // Si no es admin, bloquear vista restaurants
            if (!this.isAdmin && dashboardId === 'restaurants') {
                alert('Solo los administradores pueden ver el detalle de todos los restaurantes.');
                return;
            }
            this.currentDashboard = dashboardId;
            await this.loadDashboardData();
        },
        
        formatDisplayDate(dateString) {
            if (!dateString) return '';
            const [year, month, day] = dateString.split('-');
            return `${day}/${month}/${year}`;
        },
        
        async loadRestaurants() {
            try {
                const response = await apiService.getRestaurants();
                if (response.success) {
                    this.restaurants = response.data || [];
                    
                    // Guardar nombre del restaurante del usuario
                    if (!this.isAdmin && this.userRestaurantCode) {
                        const userRest = this.restaurants.find(r => 
                            String(r.id) === String(this.userRestaurantCode)
                        );
                        if (userRest) {
                            this.userRestaurantName = userRest.name;
                        }
                    }
                }
            } catch (error) {
                console.error('Error cargando restaurantes:', error);
            }
        },
        
        async changeRestaurant() {
            // Si no es admin, no permitir cambiar de restaurante
            if (!this.isAdmin && this.selectedRestaurant !== this.userRestaurantCode) {
                this.selectedRestaurant = this.userRestaurantCode;
                alert('Solo puedes ver tu restaurante asignado');
                return;
            }
            await this.loadDashboardData();
        },
        
        async setDatePreset(preset) {
            this.datePreset = preset;
            const today = new Date();
            
            if (preset === 'today') {
                this.selectedDate = today.toISOString().split('T')[0];
            } else if (preset === 'yesterday') {
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                this.selectedDate = yesterday.toISOString().split('T')[0];
            }
            
            await this.loadDashboardData();
        },
        
        async onDateInputChange(event) {
            const newDate = event.target.value;
            if (newDate) {
                this.selectedDate = newDate;
                this.datePreset = 'custom';
                await this.loadDashboardData();
            }
        },
        
        async applyTableFilter() {
            if (!this.isAdmin) {
                this.tableRestaurants = [this.userRestaurantCode];
            }
            if (this.currentDashboard === 'restaurants') {
                await this.loadDashboardData();
            }
        },
        
        toggleRestaurant(restId) {
            if (this.tableRestaurants.includes('all')) {
                this.tableRestaurants = [restId];
            } else {
                const index = this.tableRestaurants.indexOf(restId);
                if (index > -1) {
                    this.tableRestaurants.splice(index, 1);
                    if (this.tableRestaurants.length === 0) {
                        this.tableRestaurants = ['all'];
                    }
                } else {
                    this.tableRestaurants.push(restId);
                }
            }
        },
        
        toggleAllRestaurants() {
            if (this.isAllSelected) {
                this.tableRestaurants = [];
            } else {
                this.tableRestaurants = ['all'];
            }
        },
        
        async loadDashboardData() {
            this.loading = true;
            try {
                if (this.currentDashboard === 'restaurants') {
                    const restaurants = this.isAdmin ? this.tableRestaurants : [this.userRestaurantCode];
                    
                    const params = {
                        start_date: this.tableStartDate,
                        end_date: this.tableEndDate,
                        restaurants: restaurants
                    };
                    
                    const response = await apiService.getDashboardData('restaurants', params);
                    const data = response.data || response;
                    this.tableData = data.table || [];
                    
                } else {
                    const params = {
                        date: this.selectedDate,
                        preset: this.datePreset,
                        restaurant: this.selectedRestaurant
                    };
                    
                    const response = await apiService.getDashboardData(this.currentDashboard, params);
                    const data = response.data || response;
                    this.kpis = data.kpis || [];
                    this.secondaryMetrics = data.secondary_metrics || [];
                    this.charts = data.charts || [];
                }
            } catch (error) {
                console.error('Error cargando datos:', error);
                if (this.currentDashboard === 'restaurants') {
                    this.tableData = [];
                } else {
                    this.kpis = [];
                    this.secondaryMetrics = [];
                    this.charts = [];
                }
            } finally {
                this.loading = false;
            }
        }
    }
}).mount('#app');