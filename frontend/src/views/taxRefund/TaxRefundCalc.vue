<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <template #header><span>生产企业免抵退计算器</span></template>
      <el-form :model="form" label-width="160px" label-position="left">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="出口FOB金额">
              <el-input type="number" v-model="form.export_amount_fob" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="退税率(%)">
              <el-input type="number" v-model="form.refund_rate" :min="0" :max="17" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="征税率(%)">
              <el-input type="number" v-model="form.tax_rate" :min="0" :max="17" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="内销销项税额">
              <el-input type="number" v-model="form.domestic_tax" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="进项税额">
              <el-input type="number" v-model="form.input_tax" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上期留抵税额">
              <el-input type="number" v-model="form.last_period_deduction" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" @click="calculate" :loading="loading" size="large">计算免抵退税额</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 计算结果 -->
    <el-card v-if="result">
      <template #header><span style="font-size: 16px">📊 计算结果</span></template>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">不得免征和抵扣税额</div>
            <div style="font-size: 24px; font-weight: bold; color: #e6a23c">{{ result.non_deductible_amount }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">当期应纳税额</div>
            <div style="font-size: 24px; font-weight: bold" :style="{ color: result.taxable_amount > 0 ? '#f56c6c' : '#67c23a' }">{{ result.taxable_amount }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">当期免抵退税额</div>
            <div style="font-size: 24px; font-weight: bold; color: #409eff">{{ result.refundable_amount }}</div>
          </el-card>
        </el-col>
      </el-row>
      <el-row :gutter="20" style="margin-top: 16px">
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">应退税额</div>
            <div style="font-size: 24px; font-weight: bold; color: #67c23a">{{ result.actual_refund }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">免抵税额</div>
            <div style="font-size: 24px; font-weight: bold; color: #409eff">{{ result.exemption_amount }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" style="text-align: center">
            <div style="font-size: 12px; color: #909399">当期留抵税额</div>
            <div style="font-size: 24px; font-weight: bold; color: #e6a23c">{{ result.current_deduction }}</div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { taxRefundApi } from '../../api/business'

const loading = ref(false)
const result = ref(null)

const form = reactive({
  export_amount_fob: 100000,
  refund_rate: 13,
  tax_rate: 13,
  domestic_tax: 50000,
  input_tax: 80000,
  last_period_deduction: 0,
})

async function calculate() {
  loading.value = true
  try {
    result.value = await taxRefundApi.calculate(form)
    ElMessage.success('计算完成')
  } catch (e) {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>
