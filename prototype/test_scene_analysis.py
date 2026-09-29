import unittest
from scene_analysis import classify_scene, analyze, window_records

def record(row=1, **kw):
    return dict(dict(row=row,merchant='',item='',kind='',note='',payment='',status='未提供（PDF）',direction='支出',cents=10000,time='2026-09-28 10:00:00',platform='支付宝',id=str(row),merchant_id='/',refund=False),**kw)

class SceneAnalysisTests(unittest.TestCase):
    def test_rental_not_loan_when_rent_paid_to_bank(self):
        r=record(merchant='四川新网银行股份有限公司',item='支付租金')
        self.assertEqual(classify_scene(r)['scene'],'rental')
        self.assertEqual(classify_scene(r)['event'],'租赁付款线索')
    def test_no_rental_from_coupon_or_phone_alone(self):
        self.assertIsNone(classify_scene(record(merchant='商户',item='iPhone 手机',payment='银行&芝麻租赁专享券')))
    def test_marketing_income_is_not_loan_disbursement(self):
        r=classify_scene(record(merchant='网商贷',item='现金红包-来自网商贷',direction='收入',cents=7))
        self.assertEqual(r['scene'],'loan');self.assertEqual(r['event'],'营销收入')
    def test_loan_and_repayment_require_explicit_words(self):
        self.assertEqual(classify_scene(record(merchant='无锡锡商银行股份有限公司',item='用户还款'))['event'],'还款文字线索')
        self.assertIsNone(classify_scene(record(merchant='某银行',item='普通购物')))
    def test_recycling_does_not_imply_sale_for_spend(self):
        self.assertEqual(classify_scene(record(merchant='北京转转'))['event'],'平台支出')
        self.assertIsNone(classify_scene(record(merchant='店铺',item='山姆会员卡副卡回收')))
    def test_zero_and_neutral_records_kept_and_order_linked(self):
        a=record(1,merchant='探物租赁',merchant_id='ORDER12345')
        b=record(2,merchant_id='ORDER12345',item='用户关单解冻',direction='中性交易',cents=0)
        c=record(3,merchant_id='OTHER12345',item='用户关单解冻',direction='中性交易',cents=0)
        d=analyze([a,b,c],'2026-09-28')
        hits=d['matches'];self.assertEqual(len(hits),2)
        self.assertEqual(hits[1]['channel'],'探物租赁');self.assertIn('关联',hits[1]['basis'])
        self.assertEqual(d['scenes']['rental']['count'],2)
        self.assertEqual(d['scenes']['rental']['expense'],10000)
    def test_window_is_inclusive_and_future_excluded(self):
        rows=[record(1,time='2026-09-22 00:00:00'),record(2,time='2026-09-21 23:59:59'),record(3,time='2026-09-29 00:00:00')]
        self.assertEqual([r['row'] for r in window_records(rows,'2026-09-28',7)],[1])
    def test_no_credit_or_identity_inferences(self):
        d=analyze([record(1,kind='转账',cents=52000),record(2,item='工资',direction='收入')],'2026-09-28')
        text=str(d['profiles']);self.assertNotIn('情侣',text);self.assertNotIn('信用优',text)
        self.assertIn('薪资文字',text)

if __name__=='__main__':unittest.main()
