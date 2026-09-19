import unittest, datetime as dt, tempfile, hashlib, json, types, os
from pathlib import Path
from unittest.mock import patch, Mock
import reel_publisher as m
class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
        self.at=dt.datetime(2026,9,20,12,tzinfo=m.KST)
        self.q={'account':'phyedu_en','timezone':'Asia/Seoul','slots':{'B':'12:00','A':'18:00'},'paused':False,'queue':[],'done':[]}
        self.c={'username':'phyedu_en','user_id':'123','access_token':'NOT_A_REAL_TOKEN','obtained_at':self.at.isoformat()}
        self.args=types.SimpleNamespace(plan=False,check=False,auto=True,slot=None)
        self.ps=[patch.object(m,'DATA',self.data),patch.object(m,'QUEUE',self.data/'queue.json'),patch.object(m,'LOG',self.data/'UPLOAD.log'),
                 patch.object(m,'now',return_value=self.at),patch.object(m,'ACCOUNT','phyedu_en'),patch.object(m,'LANGUAGE','en'),
                 patch.object(m,'SECRET_NAME','IG_EN_SECRETS_JSON'),patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'owner/repo'},clear=True)]
        for p in self.ps:p.start()
        self.addCleanup(self.cleanup)
    def cleanup(self):
        for p in reversed(self.ps):p.stop()
        self.tmp.cleanup()
    def item(self):
        (self.data/'video.mp4').write_bytes(b'test video')
        (self.data/'caption.txt').write_text('Physics explained.',encoding='utf-8')
        row={'id':'test-en','video':'video.mp4','caption':'caption.txt','language':'en','reviewed':True,'slot':'B','scheduled_at':self.at.isoformat()}
        for k in ('video','caption'):row[k+'_sha256']=hashlib.sha256((self.data/row[k]).read_bytes()).hexdigest()
        self.q['queue']=[row];return row
    def run_api(self,api,persist=None):
        with patch.object(m,'load_queue',return_value=self.q),patch.object(m,'credentials',return_value=self.c),patch.object(m,'API',return_value=api),patch.object(m,'persist',side_effect=persist),patch.object(m,'host_url',return_value='https://example.com/video.mp4'):
            return m.run(self.args)
    def api(self):
        return types.SimpleNamespace(verify=Mock(),recent=Mock(return_value=[]),publishing_limit=Mock(),create=Mock(return_value='c1'),ready=Mock(),publish=Mock(return_value='m1'),
            media_info=Mock(return_value={'id':'m1','caption':'Physics explained.','timestamp':self.at.isoformat(),'permalink':'https://www.instagram.com/reel/test/'}))
    def test_wrong_account_queue_rejected(self):
        self.q['account']='phyedu_net';m.save_queue(self.q)
        with self.assertRaises(RuntimeError):m.load_queue()
    def test_wrong_account_credential_rejected(self):
        with patch.dict(os.environ,{'IG_EN_SECRETS_JSON':json.dumps(dict(self.c,username='someone_else'))}):
            with self.assertRaises(RuntimeError):m.credentials()
    def test_korean_credential_extracts_only_target(self):
        raw={'accounts':{'phyedu_net':dict(self.c,user_id='456'),'ha_miltonian':{'access_token':'OTHER'}}}
        with patch.object(m,'LANGUAGE','ko'),patch.object(m,'ACCOUNT','phyedu_net'),patch.object(m,'SECRET_NAME','IG_SECRETS_JSON'),patch.dict(os.environ,{'IG_SECRETS_JSON':json.dumps(raw)}):
            self.assertEqual(m.credentials()['user_id'],'456');self.assertEqual(m.credentials()['username'],'phyedu_net')
    def test_tampered_or_wrong_language_media_rejected(self):
        row=self.item()
        for change in ({'language':'ko'},{'reviewed':False},{'video':'../video.mp4'},{'video_sha256':'bad'}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):m.media(dict(row,**change))
    def test_korean_caption_not_allowed_for_english(self):
        row=self.item();(self.data/row['caption']).write_text('한국어',encoding='utf-8');row['caption_sha256']=hashlib.sha256((self.data/row['caption']).read_bytes()).hexdigest()
        with self.assertRaises(RuntimeError):m.media(row)
        with patch.object(m,'LANGUAGE','ko'):m.media(dict(row,language='ko'))
    def test_read_only_check_never_creates_or_publishes(self):
        self.item();api=self.api();self.args.check=True
        self.assertEqual(self.run_api(api),0);api.verify.assert_called_once();api.publishing_limit.assert_called_once();api.publish.assert_not_called();api.create.assert_not_called()
    def test_future_no_network(self):
        self.item()['scheduled_at']=(self.at+dt.timedelta(days=1)).isoformat();api=self.api()
        self.assertEqual(self.run_api(api),0);api.verify.assert_not_called()
    def test_live_identity_mismatch_blocks_post(self):
        self.item();api=self.api();api.verify.side_effect=RuntimeError('wrong account')
        with self.assertRaises(RuntimeError):self.run_api(api)
        api.create.assert_not_called();api.publish.assert_not_called()
    def test_remote_daily_cap_blocks_post(self):
        self.item();api=self.api();api.recent.return_value=[{'timestamp':self.at.isoformat(),'caption':'other'}]*2
        self.run_api(api);api.create.assert_not_called();api.publish.assert_not_called()
    def test_duplicate_reconciles_without_publish(self):
        self.item();api=self.api();api.recent.return_value=[dict(api.media_info.return_value)]
        self.run_api(api);self.assertEqual(len(self.q['queue']),0);api.publish.assert_not_called()
    def test_uncertain_request_never_republished(self):
        self.item()['publish_requested_at']=self.at.isoformat();api=self.api()
        self.assertEqual(self.run_api(api),1);self.assertTrue(self.q['paused']);api.publish.assert_not_called()
    def test_confirmed_id_reconciles(self):
        self.item()['media_id']='m1';api=self.api();self.run_api(api);api.publish.assert_not_called();self.assertEqual(len(self.q['done']),1)
    def test_intent_persisted_before_publish(self):
        row=self.item();api=self.api();records=[]
        def save(q,why):records.append((why,bool(row.get('publish_requested_at'))))
        def publish(cid):
            self.assertIn(('publication intent',True),records);return 'm1'
        api.publish.side_effect=publish
        self.run_api(api,save);self.assertEqual(self.q['done'][0]['media_id'],'m1')
    def test_failed_intent_persistence_blocks_publish(self):
        self.item();api=self.api()
        def save(q,why):
            if why=='publication intent':raise RuntimeError('push failed')
        with self.assertRaises(RuntimeError):self.run_api(api,save)
        api.publish.assert_not_called()
    def test_processing_failure_retains_queue_without_publish(self):
        self.item();api=self.api();api.ready.side_effect=m.ProcessingError()
        self.assertEqual(self.run_api(api),1);self.assertEqual(len(self.q['queue']),1);api.publish.assert_not_called()
    def test_timeout_after_publish_retains_intent(self):
        row=self.item();api=self.api();api.publish.side_effect=RuntimeError('uncertain')
        with self.assertRaises(RuntimeError):self.run_api(api)
        self.assertIn('publish_requested_at',row);self.assertEqual(len(self.q['queue']),1)
if __name__=='__main__':unittest.main()
