const UserManagement = {
    emits: ['close', 'password-changed'],
    template: `
        <div class="user-management-overlay" @click.self="close">
            <div class="user-management-modal">
                <div class="modal-header">
                    <h2><i class="fas fa-users-cog"></i> Gestión de Usuarios</h2>
                    <button class="close-btn" @click="close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <!-- Lista de Usuarios -->
                    <div class="users-section">
                        <h3><i class="fas fa-list"></i> Usuarios del Sistema</h3>
                        
                        <div v-if="loading" class="loading-state">
                            <i class="fas fa-spinner fa-spin"></i> Cargando usuarios...
                        </div>
                        
                        <div v-else-if="error" class="error-state">
                            <i class="fas fa-exclamation-triangle"></i> {{ error }}
                        </div>
                        
                        <div v-else class="users-table-wrapper">
                            <table class="users-table">
                                <thead>
                                    <tr>
                                        <th>Usuario</th>
                                        <th>Rol</th>
                                        <th>Restaurante</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="user in users" :key="user.username" 
                                        :class="{ 'selected': selectedUser === user.username, 'inactive': !user.is_active }">
                                        <td>
                                            <div class="user-cell">
                                                <div class="user-avatar-small" :class="user.role">
                                                    {{ getInitials(user.username) }}
                                                </div>
                                                <span class="username">{{ user.username }}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <span class="role-badge" :class="user.role">
                                                <i :class="user.role === 'admin' ? 'fas fa-crown' : 'fas fa-store'"></i>
                                                {{ user.role === 'admin' ? 'Admin' : 'Restaurante' }}
                                            </span>
                                        </td>
                                        <td>
                                            <span v-if="user.restaurant_name" class="restaurant-tag">
                                                <i class="fas fa-map-marker-alt"></i>
                                                {{ user.restaurant_name }}
                                            </span>
                                            <span v-else-if="user.unified_team_sk" class="restaurant-tag">
                                                <i class="fas fa-hashtag"></i>
                                                {{ user.unified_team_sk }}
                                            </span>
                                            <span v-else class="no-restaurant">-</span>
                                        </td>
                                        <td>
                                            <span class="status-badge" :class="user.is_active ? 'active' : 'inactive'">
                                                <i :class="user.is_active ? 'fas fa-check-circle' : 'fas fa-ban'"></i>
                                                {{ user.is_active ? 'Activo' : 'Inactivo' }}
                                            </span>
                                        </td>
                                        <td>
                                            <button class="action-btn change-pass" 
                                                    @click="selectUser(user)"
                                                    :class="{ 'active': selectedUser === user.username }">
                                                <i class="fas fa-key"></i>
                                                Cambiar Contraseña
                                            </button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- Panel de Cambio de Contraseña -->
                    <div v-if="selectedUser" class="password-panel" :class="{ 'show': selectedUser }">
                        <div class="panel-header">
                            <i class="fas fa-lock"></i>
                            <h4>Cambiar contraseña de: <strong>{{ selectedUser }}</strong></h4>
                        </div>
                        
                        <div class="form-group">
                            <label>Nueva Contraseña</label>
                            <div class="password-input-wrapper">
                                <input 
                                    :type="showPassword ? 'text' : 'password'" 
                                    v-model="newPassword"
                                    placeholder="Ingrese nueva contraseña"
                                    @keyup.enter="changePassword"
                                    ref="passwordInput"
                                >
                                <button class="toggle-password" @click="showPassword = !showPassword">
                                    <i :class="showPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                                </button>
                            </div>
                            <small class="help-text">
                                <i class="fas fa-info-circle"></i>
                                Mínimo 4 caracteres. Para restaurantes, se recomienda usar su código.
                            </small>
                        </div>
                        
                        <div class="password-actions">
                            <button class="btn-cancel" @click="cancelChange">
                                <i class="fas fa-times"></i> Cancelar
                            </button>
                            <button class="btn-save" 
                                    @click="changePassword" 
                                    :disabled="!canSave || saving">
                                <i :class="saving ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
                                {{ saving ? 'Guardando...' : 'Guardar Contraseña' }}
                            </button>
                        </div>
                        
                        <!-- Mensajes de resultado -->
                        <div v-if="message" class="result-message" :class="message.type">
                            <i :class="message.type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle'"></i>
                            {{ message.text }}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    data() {
        return {
            users: [],
            loading: false,
            error: null,
            selectedUser: null,
            newPassword: '',
            showPassword: false,
            saving: false,
            message: null
        }
    },
    computed: {
        canSave() {
            return this.newPassword && this.newPassword.length >= 4;
        }
    },
    mounted() {
        this.loadUsers();
        // Cerrar con ESC
        document.addEventListener('keydown', this.handleEsc);
    },
    beforeUnmount() {
        document.removeEventListener('keydown', this.handleEsc);
    },
    methods: {
        handleEsc(e) {
            if (e.key === 'Escape') this.close();
        },
        async loadUsers() {
            this.loading = true;
            this.error = null;
            try {
                const response = await apiService._fetch(`${API_BASE_URL}/auth/admin/users`);
                this.users = response;
            } catch (err) {
                this.error = 'Error cargando usuarios: ' + err.message;
                console.error(err);
            } finally {
                this.loading = false;
            }
        },
        getInitials(username) {
            return username.slice(0, 2).toUpperCase();
        },
        selectUser(user) {
            this.selectedUser = user.username;
            this.newPassword = '';
            this.showPassword = false;
            this.message = null;
            // Focus en el input después de renderizar
            this.$nextTick(() => {
                this.$refs.passwordInput?.focus();
            });
        },
        cancelChange() {
            this.selectedUser = null;
            this.newPassword = '';
            this.message = null;
        },
        async changePassword() {
            if (!this.canSave) return;
            
            this.saving = true;
            this.message = null;
            
            try {
                const response = await apiService._fetch(
                    `${API_BASE_URL}/auth/admin/users/reset-password`,
                    {
                        method: 'POST',
                        body: JSON.stringify({
                            target_username: this.selectedUser,
                            new_password: this.newPassword
                        })
                    }
                );
                
                this.message = {
                    type: 'success',
                    text: response.message
                };
                
                this.newPassword = '';
                this.$emit('password-changed', this.selectedUser);
                
                // Cerrar panel después de 2 segundos
                setTimeout(() => {
                    this.selectedUser = null;
                    this.message = null;
                }, 2000);
                
            } catch (err) {
                this.message = {
                    type: 'error',
                    text: 'Error: ' + err.message
                };
            } finally {
                this.saving = false;
            }
        },
        close() {
            this.$emit('close');
        }
    }
};