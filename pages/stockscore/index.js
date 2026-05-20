Page({
  data: {
    loading: true,
    stocks: []
  },
  onLoad() {
    // TODO: 替换为真实后端API
    this.setData({
      stocks: [
        {
          code: '600519',
          name: '贵州茅台',
          score: 92,
          factors: [
            { name: '成长性', value: '优秀' },
            { name: '估值', value: '合理' },
            { name: '流动性', value: '高' }
          ],
          reason: '公司业绩持续增长，行业龙头，估值合理，流动性强。'
        },
        {
          code: '000858',
          name: '五粮液',
          score: 85,
          factors: [
            { name: '成长性', value: '良好' },
            { name: '估值', value: '偏高' },
            { name: '流动性', value: '高' }
          ],
          reason: '业绩稳定，品牌优势明显，但估值略高。'
        }
      ],
      loading: false
    });
  }
});
