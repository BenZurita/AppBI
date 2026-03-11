const Sidebar = {
    props: ['currentDashboard', 'isOpen', 'userRole', 'unifiedTeamSk'],
    emits: ['change-dashboard', 'close-sidebar', 'logout', 'open-user-management'],
    template: `
        <aside class="sidebar" :class="{ 'open': isOpen }">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <i class="fas fa-chart-line"></i>
                    <span>App BI</span>
                </div>
                <button class="close-btn" @click="closeSidebar">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <nav>
                <ul class="nav-menu">
                    <li class="nav-item" 
                        v-for="dash in allDashboards" 
                        :key="dash.id"
                        @click="selectDashboard(dash.id)">
                        <button class="nav-link" :class="{ active: currentDashboard === dash.id }">
                            <i :class="dash.icon"></i>
                            <span>{{ dash.name }}</span>
                        </button>
                    </li>
                </ul>
            </nav>
            
            <!-- SECCIÓN ADMIN: Gestión de Usuarios -->
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
                <div class="user-info" @click="logout" style="cursor: pointer;">
                    <div class="user-avatar">{{ userInitials }}</div>
                    <div style="display: flex; flex-direction: column;">
                        <span style="font-weight: 600;">{{ displayName }}</span>
                        <small style="color: var(--text-secondary); font-size: 0.75rem;">{{ userRole === 'admin' ? 'Administrador' : 'Restaurante' }}</small>
                    </div>
                    <i class="fas fa-sign-out-alt" style="margin-left: auto; color: #ef4444;"></i>
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
                { id: 'productmix', name: 'Product Mix', icon: 'fas fa-chart-pie' },
                { id: 'hours', name: 'Ventas por Hora', icon: 'fas fa-clock' }
            ]
        }
    },
    methods: {
        selectDashboard(id) {
            this.$emit('change-dashboard', id);
            if (window.innerWidth <= 768) {
                this.$emit('close-sidebar');
            }
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
            if (window.innerWidth <= 768) {
                this.$emit('close-sidebar');
            }
        }
    }
};