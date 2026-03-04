const KPICard = {
    props: ['kpi'],
    template: `
        <div class="kpi-card-horizontal">
            <!-- Icono y Título a la izquierda -->
            <div class="kpi-left">
                <div class="kpi-icon-horiz" :class="kpi.color">
                    <i :class="kpi.icon"></i>
                </div>
                <div class="kpi-title-horiz">{{ kpi.title }}</div>
            </div>
            
            <!-- 4 Períodos en línea horizontal -->
            <div class="periods-container">
                <div class="period-box" v-for="(periodo, idx) in kpi.periodos" :key="idx">
                    <div class="period-name">{{ periodo.nombre }}</div>
                    <div class="period-value">{{ periodo.valor }}</div>
                    <div class="period-comp">{{ periodo.comparacion }}</div>
                    <div class="period-diff" :class="periodo.trend">
                        <span class="diff-monto">{{ periodo.diff_monto }}</span>
                        <span class="diff-pct">
                            <i :class="periodo.trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                            {{ Math.abs(periodo.diff_pct) }}%
                        </span>
                    </div>
                </div>
            </div>
        </div>
    `
};