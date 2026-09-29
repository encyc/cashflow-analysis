import unittest
from datetime import datetime
from alipay_parser import parse_alipay_row
from merge_reports import merge_records, validate_identity

class MultiSourceTests(unittest.TestCase):
    def test_alipay_neutral_refund_and_long_ids(self):
        r=parse_alipay_row(['不计\n收支','商户','退款-商品','银行卡','450.50','2026010100000000000000_R123','ORDER','2026-01-01\n12:00:00'],1,3,1)
        self.assertEqual(r['direction'],'中性交易')
        self.assertEqual(r['raw_direction'],'不计收支')
        self.assertEqual(r['cents'],45050)
        self.assertTrue(r['refund_indicator'])
        self.assertFalse(r['refund'])
        self.assertEqual(r['id'],'2026010100000000000000_R123')
    def test_wechat_long_order_id(self):
        from pdf_parser import parse_table_row
        r=parse_table_row(["1"*45,"2026-01-01\n12:00:00","其他","收入","/","60.00","钱包模块支付","/"],1,1,1)
        self.assertEqual(r["id"],"1"*45)

    def test_alipay_invalid_direction_and_amount(self):
        row=['未知','商户','商品','余额','1.00','1234567890123456','','2026-01-01\n12:00:00']
        with self.assertRaises(ValueError): parse_alipay_row(row,1,1,1)
        row[0]='支出';row[4]='1.001'
        with self.assertRaises(ValueError): parse_alipay_row(row,1,1,1)
    def test_cross_platform_same_id_retained(self):
        a=dict(id='abc',platform='微信',time='2026-01-01 00:00:00',cents=100,direction='收入',row=1,source_file='a',source_ref='a')
        b={**a,'platform':'支付宝','source_file':'b'}
        self.assertEqual(len(merge_records([a,b])[0]),2)
        self.assertEqual(len(merge_records([a,dict(a)])[0]),1)
        with self.assertRaises(ValueError):merge_records([a,{**a,'cents':200}])
        separate={**a,'source_ref':'another row','direction':'中性交易','time':'2026-01-01 01:00:00'}
        rows,_=merge_records([a,separate])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['same_order_records'],2)
    def test_identity_uses_both_name_and_document(self):
        validate_identity(('姓名','document-a'),('姓名','document-a'))
        with self.assertRaises(ValueError):validate_identity(('姓名','document-a'),('姓名','document-b'))
        with self.assertRaises(ValueError):validate_identity(('姓名',''),('姓名',''))

if __name__=='__main__':unittest.main()
