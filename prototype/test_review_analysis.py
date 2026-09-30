import copy
import unittest

from scene_analysis import analyze, classify_scene
from test_scene_analysis import record


class ReviewAnalysisTests(unittest.TestCase):
    def test_refund_item_takes_precedence_over_credit_repayment(self):
        hit = classify_scene(record(merchant='花呗', item='退款-还款', direction='收入'))
        self.assertEqual(hit['event'], '退款记录')

    def test_credit_repayment_separated_from_loan(self):
        hit = classify_scene(record(merchant='花呗', item='主动还款'))
        self.assertEqual(hit['scene'], 'credit')
        self.assertEqual(hit['event'], '还款文字线索')

    def test_credit_merchant_text_and_neutral_direction_preserved(self):
        hit = classify_scene(record(merchant='信用卡还款', direction='中性交易'))
        self.assertEqual(hit['scene'], 'credit')
        self.assertEqual(hit['event'], '还款文字（原标非支出）')

    def test_payment_method_alone_does_not_imply_credit_repayment(self):
        self.assertIsNone(classify_scene(record(merchant='普通商店', item='日用品', payment='花呗&信用卡')))

    def test_explicit_loan_product_not_confused_with_credit_brand(self):
        hit = classify_scene(record(merchant='抖音月付', item='放心借还款'))
        self.assertEqual(hit['scene'], 'loan')

    def test_credit_period_excludes_loan_refund_and_marketing_from_repayments(self):
        rows = [record(1, merchant='花呗', item='还款', cents=500),
                record(2, merchant='借呗', item='还款', cents=700),
                record(3, merchant='花呗', item='退款', refund_indicator=True, direction='收入', cents=100),
                record(4, merchant='花呗', item='奖励红包', direction='收入', cents=2)]
        data = analyze(rows, '2026-09-28')
        periods = data.get('credit_periods', [])
        self.assertTrue(periods, 'credit periods must be published separately')
        self.assertEqual((periods[0]['count'], periods[0]['repayment'], periods[0]['marketing']), (3, 500, 2))
        self.assertEqual(data['loan_periods'][0]['expense'], 700)

    def test_salary_excludes_refunds_payments_and_credit_related_text(self):
        rows = [record(1, item='八月工资', direction='收入', cents=500000),
                record(2, item='工资退还', direction='收入', cents=20000),
                record(3, item='工资', direction='支出', cents=10000),
                record(4, item='工资卡充值', direction='收入', cents=9000),
                record(5, item='工资', direction='中性交易', cents=8000),
                record(6, item='贷款发放用于工资', direction='收入', cents=7000),
                record(7, item='工资', status='交易失败', direction='收入', cents=6000),
                record(8, merchant='薪资代发', direction='收入', cents=50000)]
        salary = analyze(rows, '2026-09-28').get('review', {}).get('salary', {})
        self.assertEqual(salary.get('rows'), [1, 8])
        self.assertEqual(salary['income'], 550000)

    def test_salary_months_fill_missing_month_and_preserve_sources(self):
        rows = [record(1, merchant='单位甲', note='工资', direction='收入', cents=100, time='2026-01-30 10:00:00'),
                record(2, merchant='单位甲', item='薪资', direction='收入', cents=200, time='2026-03-02 10:00:00')]
        salary = analyze(rows, '2026-03-31').get('review', {}).get('salary', {})
        self.assertEqual([(m['month'], m['income']) for m in salary.get('monthly', [])],
                         [('2026-01', 100), ('2026-02', 0), ('2026-03', 200)])
        self.assertEqual(salary['sources'][0]['rows'], [1, 2])

    def test_large_threshold_and_night_boundaries_exclude_neutral(self):
        rows = [record(1, cents=1000000, time='2026-09-28 22:00:00'),
                record(2, cents=999999, time='2026-09-28 21:59:59'),
                record(3, cents=1000001, time='2026-09-28 05:59:59', direction='收入'),
                record(4, cents=1000000, time='2026-09-28 06:00:00'),
                record(5, cents=9000000, time='2026-09-28 23:00:00', direction='中性交易')]
        review = analyze(rows, '2026-09-28').get('review', {})
        self.assertEqual(review.get('large', {}).get('rows'), [1, 3, 4])
        self.assertEqual(review['night']['rows'], [1, 3])

    def test_flow_keeps_platforms_and_directions_separate(self):
        rows = [record(1, merchant='商户甲', platform='微信', direction='收入', cents=300),
                record(2, merchant='商户甲', platform='微信', cents=100),
                record(3, merchant='商户甲', platform='支付宝', direction='收入', cents=500),
                record(4, merchant='商户甲', direction='中性交易', cents=999),
                record(5, merchant='', direction='收入', cents=20)]
        original = copy.deepcopy(rows)
        flows = analyze(rows, '2026-09-28').get('review', {}).get('flows', [])
        self.assertEqual(len(flows), 3)
        wechat = next(f for f in flows if f['platform'] == '微信')
        self.assertEqual((wechat['income'], wechat['expense'], wechat['rows']), (300, 100, [1, 2]))
        self.assertEqual(sum(f['income'] for f in flows), 820)
        self.assertEqual(rows, original)


if __name__ == '__main__':
    unittest.main()
