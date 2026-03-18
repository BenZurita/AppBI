const Sidebar = {
    props: ['currentDashboard', 'isOpen', 'userRole', 'unifiedTeamSk'],
    emits: ['change-dashboard', 'close-sidebar', 'logout', 'open-user-management'],
    template: `
        <aside class="sidebar" :class="{ 'open': isOpen }" @click.stop>
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <i class="fas fa-chart-line"></i>
                    <span>App BI</span>
                </div>
                <button class="close-btn" @click="closeSidebar" aria-label="Cerrar menú">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <nav>
                <ul class="nav-menu" role="menu">
                    <li class="nav-item" 
                        v-for="dash in allDashboards" 
                        :key="dash.id"
                        role="none">
                        <button class="nav-link" 
                                :class="{ active: currentDashboard === dash.id }"
                                @click="selectDashboard(dash.id)"
                                role="menuitem">
                            <i :class="dash.icon" aria-hidden="true"></i>
                            <span>{{ dash.name }}</span>
                        </button>
                    </li>
                </ul>
            </nav>
            
            <div v-if="userRole === 'admin'" class="admin-section">
                <div class="section-divider">
                    <span>Administración</span>
                </div>
                <button class="nav-link admin-link" @click="openUserManagement">
                    <i class="fas fa-users-cog"></i>
                    <span>Gestionar Usuarios</span>
                </button>
            </div>
            
            <div class="sidebar-footer">
                <div class="user-info" @click="logout" role="button" tabindex="0">
                    <div class="user-avatar">{{ userInitials }}</div>
                    <div class="user-details">
                        <span class="user-name">{{ displayName }}</span>
                        <small class="user-role">{{ userRole === 'admin' ? 'Administrador' : 'Restaurante ' + unifiedTeamSk }}</small>
                    </div>
                    <i class="fas fa-sign-out-alt logout-icon" aria-hidden="true"></i>
                </div>
            </div>
        </aside>
    `,
    computed: {
        userInitials() {
            if (this.userRole === 'admin') return 'AD';
            return this.unifiedTeamSk ? this.unifiedTeamSk.slice(0, 2).toUpperCase() : 'US';
        },
        displayName() {
            if (this.userRole === 'admin') return 'Admin';
            return 'Mi Cuenta';
        }
    },
    data() {
        return {
            allDashboards: [
                { id: 'daily', name: 'Daily Sales', icon: 'fas fa-calendar-day' },
                { id: 'salesbyregister', name: 'Venta por Caja', icon: 'fas fa-cash-register' },
                { id: 'productmix', name: 'Product Mix', icon: 'fas fa-chart-pie' },
                { id: 'hours', name: 'Ventas por Hora', icon: 'fas fa-clock' }
            ]
        }
    },
    methods: {
        selectDashboard(id) {
            this.$emit('change-dashboard', id);
        },
        closeSidebar() {
            this.$emit('close-sidebar');
        },
        logout() {
            this.$emit('logout');
        },
        openUserManagement() {
            console.log('[Sidebar] Abriendo gestión de usuarios...');
            this.$emit('open-user-management');
        }
    }
};