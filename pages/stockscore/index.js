const app = getApp();

const SIGNAL_LABELS = {
  strong_positive: '双目标强信号',
  absolute_upside_but_weak_relative: '上涨强，相对弱',
  relative_resilience_without_absolute_upside: '相对强，上涨弱',
  weak_negative: '双目标偏弱',
  mixed_or_neutral: '信号中性',
  insufficient_data: '数据不足'
};

const TARGET_LABELS = {
  up: '未来20日上涨',
  outperform: '跑赢沪深300'
};

const FEATURE_LABELS = {
  net_mf_amount_ratio: '主力净流入',
  margin_buy_ratio: '融资买入',
  pledge_ratio: '质押比例',
  hk_hold_ratio: '北向持股',
  ret_20: '20日动量',
  ma60_bias: '60日均线偏离',
  vol_20: '20日波动',
  amount_ratio_20: '成交额强度'
};

Page({
  data: {
    tsCode: '001390.SZ',
    tradeDate: '20260401',
    loading: false,
    error: '',
    diagnosis: null,
    targets: [],
    warnings: []
  },

  onLoad() {
    this.fetchDiagnosis();
  },

  onTsCodeInput(event) {
    this.setData({ tsCode: event.detail.value.trim().toUpperCase() });
  },

  onTradeDateInput(event) {
    this.setData({ tradeDate: event.detail.value.trim() });
  },

  fetchDiagnosis() {
    const tsCode = this.data.tsCode;
    const tradeDate = this.data.tradeDate;
    if (!tsCode || !tradeDate) {
      this.setData({ error: '请输入股票代码和交易日。' });
      return;
    }

    this.setData({ loading: true, error: '' });
    wx.request({
      url: `${app.globalData.apiBaseUrl}/quant/stock-diagnosis/`,
      method: 'GET',
      data: {
        ts_code: tsCode,
        trade_date: tradeDate
      },
      success: (response) => {
        if (response.statusCode !== 200) {
          const message = response.data && response.data.error ? response.data.error : '诊断请求失败。';
          this.setData({ loading: false, error: message, diagnosis: null, targets: [], warnings: [] });
          return;
        }
        this.setDiagnosis(response.data);
      },
      fail: () => {
        this.setData({
          loading: false,
          error: '无法连接诊断服务，请确认后端已启动。',
          diagnosis: null,
          targets: [],
          warnings: []
        });
      }
    });
  },

  setDiagnosis(data) {
    const signal = data.combined_signal || {};
    const diagnosis = {
      tsCode: data.ts_code,
      stockName: data.stock_name || '--',
      industry: data.industry || '--',
      tradeDate: data.trade_date,
      modelRole: data.model_role === 'fallback' ? 'Fallback' : 'Primary',
      signalLabel: SIGNAL_LABELS[signal.label] || signal.label || '--',
      signalDescription: signal.description || '',
      confidence: signal.confidence || '--',
      upDecile: signal.up_decile || '--',
      outperformDecile: signal.outperform_decile || '--'
    };
    const targets = Object.keys(data.targets || {}).map((key) => this.targetView(key, data.targets[key]));
    const warnings = (data.warnings || []).map((item) => this.warningView(item));
    this.setData({
      loading: false,
      error: '',
      diagnosis,
      targets,
      warnings
    });
  },

  targetView(key, target) {
    return {
      key,
      label: TARGET_LABELS[key] || key,
      decile: target.score_decile || '--',
      rank: this.formatPercent(target.score_pct_rank),
      cohort: this.cohortLabel(target.cohort),
      score: this.formatNumber(target.score),
      futureReturn: this.formatSignedPercent(target.observed && target.observed.future_ret_20),
      futureExcess: this.formatSignedPercent(target.observed && target.observed.future_excess_ret_20),
      positive: (target.top_positive_contributions || []).slice(0, 4).map((item) => this.contributionView(item)),
      negative: (target.top_negative_contributions || []).slice(0, 4).map((item) => this.contributionView(item))
    };
  },

  contributionView(item) {
    return {
      feature: FEATURE_LABELS[item.feature] || item.feature,
      raw: this.formatNumber(item.raw_value),
      contribution: this.formatSignedNumber(item.contribution)
    };
  },

  warningView(text) {
    const prefix = String(text).split(':')[0];
    const labels = {
      fallback_model_used: '使用实验性Fallback模型',
      rolling_validation_window: '处于2026滚动验证窗口',
      outside_validation_windows: '日期不在验证窗口内',
      neutral_score: '分位接近市场中位',
      many_missing_features: '较多特征经过缺失值填充',
      target_disagreement: '两个目标信号分歧较大',
      observed_label_conflict: '历史上涨和跑赢标签冲突',
      low_combined_confidence: '综合置信度偏低'
    };
    return labels[prefix] || text;
  },

  cohortLabel(value) {
    const labels = {
      top: 'Top',
      upper: '偏高',
      middle: '中性',
      lower: '偏低',
      bottom: 'Bottom'
    };
    return labels[value] || value || '--';
  },

  formatPercent(value) {
    if (value === null || value === undefined) return '--';
    return `${Math.round(Number(value) * 1000) / 10}%`;
  },

  formatSignedPercent(value) {
    if (value === null || value === undefined) return '--';
    const percent = Number(value) * 100;
    const prefix = percent > 0 ? '+' : '';
    return `${prefix}${Math.round(percent * 10) / 10}%`;
  },

  formatNumber(value) {
    if (value === null || value === undefined) return '--';
    const number = Number(value);
    if (Number.isNaN(number)) return '--';
    return `${Math.round(number * 10000) / 10000}`;
  },

  formatSignedNumber(value) {
    if (value === null || value === undefined) return '--';
    const number = Number(value);
    if (Number.isNaN(number)) return '--';
    const prefix = number > 0 ? '+' : '';
    return `${prefix}${Math.round(number * 10000) / 10000}`;
  }
});
