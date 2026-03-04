const Sidebar = {
    props: ['currentDashboard', 'isOpen'],
    emits: ['change-dashboard', 'close-sidebar'],
    template: `
        <aside class="sidebar" :class="{ 'open': isOpen }">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <i class="fas fa-chart-pie"></i>
                    <span>App BI</span>
                </div>
                <button class="close-btn" @click="closeSidebar">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <nav>
                <ul class="nav-menu">
                    <li class="nav-item" 
                        v-for="dash in dashboards" 
                        :key="dash.id"
                        @click="selectDashboard(dash.id)">
                        <button class="nav-link" :class="{ active: currentDashboard === dash.id }">
                            <i :class="dash.icon"></i>
                            <span>{{ dash.name }}</span>
                        </button>
                    </li>
                </ul>
            </nav>
            
            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-avatar">BZ</div>
                    <span>Mi Cuenta</span>
                </div>
            </div>
        </aside>
    `,
    data() {
        return {
            dashboards: [
                { id: 'daily', name: 'Daily Sales', icon: 'fas fa-calendar-day' },
                { id: 'restaurants', name: 'Detalle de restaurantes', icon: 'fas fa-store' },
                { id: 'inventario', name: 'Inventario', icon: 'fas fa-box' },
                { id: 'finanzas', name: 'Finanzas', icon: 'fas fa-dollar-sign' }
            ]
        }
        
    },
    methods: {
        selectDashboard(id) {
            this.$emit('change-dashboard', id);
            // En móvil cerrar automáticamente
            if (window.innerWidth <= 768) {
                this.$emit('close-sidebar');
            }
        },
        closeSidebar() {
            this.$emit('close-sidebar');
        }
    }
};