import unittest
from build_report import classify, cents

class ClassificationTests(unittest.TestCase):
    def test_explicit_item_beats_generic_platform(self):
        self.assertEqual(classify('商户消费','美团','花之依恋-生日鲜花','支出')[0], '鲜花礼品')
        self.assertEqual(classify('商户消费','美团','团购-订单123','支出')[0], '综合平台（用途待核）')

    def test_preserve_transfers_and_refunds(self):
        self.assertEqual(classify('转账','咖啡','转账备注','支出')[0],'转账往来')
        self.assertEqual(classify('美团-退款','美团','鲜花','收入')[0],'退款入账')

    def test_new_categories_require_transaction_evidence(self):
        cases=[('月桥婚礼策划','/','婚庆摄影'),('生活缴费','电费','生活缴费'),
               ('杭州深度求索','DeepSeek-API服务','数字服务'),('陌生商家','不详','未分类'),
               ('某公司','门诊缴费','医疗药品'),('新力有家','江西有家实业有限公司-消费','商超便利'),
               ('途虎养车','订单','车辆养护')]
        for merchant,item,expected in cases:
            with self.subTest(merchant=merchant):
                category,reason=classify('商户消费',merchant,item,'支出')
                self.assertEqual(category,expected)
                self.assertTrue(reason)

    def test_case_insensitive_keywords(self):
        self.assertEqual(classify('商户消费','广东省通信科技5G','广东省通信科技5G','支出')[0],'通信服务')

    def test_money_no_float_rounding_or_silent_precision_loss(self):
        self.assertEqual(cents('1,234.56'),123456)
        with self.assertRaises(ValueError): cents('1.001')

class PdfTests(unittest.TestCase):
    def test_wrapped_identifiers_and_missing_fields(self):
        from pdf_parser import parse_table_row
        r=parse_table_row(['420000315120260928539062\n4460','2026-09-28\n12:06:44','商户消费','支出','招商银行储\n蓄卡(1649)','18.00','广州湘悠悠\n（天河店）','20260928000000101\n894964096000187'],1,5,1)
        self.assertEqual(r['id'],'4200003151202609285390624460')
        self.assertEqual(r['cents'],1800)
        self.assertEqual(r['time'],'2026-09-28 12:06:44')
        self.assertEqual(r['payment'],'招商银行储蓄卡(1649)')
        self.assertEqual(r['merchant'],'广州湘悠悠（天河店）')
        self.assertEqual(r['status'],'未提供（PDF）')
        self.assertEqual(r['source_page'],1)

    def test_bad_pdf_money_and_unknown_direction_fail(self):
        from pdf_parser import parse_table_row
        row=['12345678901234567890123456','2026-01-01\n12:00:00','转账','支出','零钱','坏金额','某人','/']
        with self.assertRaises(ValueError):parse_table_row(row,1,1,1)
        row[5]='20.00';row[3]='不明'
        with self.assertRaises(ValueError):parse_table_row(row,1,1,1)

class ReconciliationTests(unittest.TestCase):
    def test_same_amount_is_not_identity_and_conflicts_remain_visible(self):
        from compare_reports import reconcile
        base=dict(time='2026-01-10 12:00:00',cents=100,direction='支出',payment='零钱',merchant_id='m',
                  merchant='商家',kind='商户消费',category='未分类',row=19,source_page=1,source_table_row=2)
        meta=dict(start='2026-01-01',end='2026-01-31')
        a=dict(meta=meta,records=[dict(base,id='same'),dict(base,id='only-excel')])
        b=dict(meta=meta,records=[dict(base,id='same',cents=200),dict(base,id='only-pdf')])
        result=reconcile(a,b)
        self.assertEqual(result['matched'],1)
        self.assertEqual(result['excel_only'],['only-excel'])
        self.assertEqual(result['pdf_only'],['only-pdf'])
        self.assertEqual(result['field_differences']['cents'],1)

    def test_nonoverlap_periods_are_not_missing_records(self):
        from compare_reports import reconcile
        r=dict(id='early',time='2025-09-02 12:00:00',cents=100,direction='支出')
        a=dict(meta=dict(start='2025-09-01',end='2026-09-01'),records=[r])
        b=dict(meta=dict(start='2025-09-30',end='2026-09-28'),records=[])
        result=reconcile(a,b)
        self.assertEqual(result['excel_only'],[])
        self.assertEqual(result['excel_outside']['count'],1)

if __name__=='__main__':unittest.main()
