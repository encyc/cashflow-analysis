(function () {
  'use strict';

  // 与服务端 MAX_UPLOAD_MB 默认值保持一致；如修改 .env 请同步此处
  var MAX_MB = 100;
  var ALLOWED_EXT = ['zip', 'pdf', 'xlsx', 'xls'];

  var state = { platform: '' };

  var guides = {
    wechat: {
      title: '如何在微信中导出流水',
      steps: [
        '打开微信，进入「我 → 服务 → 钱包 → 账单」；',
        '点击右上角「常见问题 → 下载账单」；',
        '选择「用于个人对账」，并选择需要的时间范围；',
        '填写本人邮箱，微信会把加密的流水文件发送到该邮箱；',
        '解压密码会通过「微信支付」公众号的服务通知发送，请记下来；',
        '到邮箱中下载附件（iPhone 请先存储到「文件」App），然后回到本页上传。'
      ]
    },
    alipay: {
      title: '如何在支付宝中导出流水',
      steps: [
        '打开支付宝，进入「我的 → 账单」；',
        '点击右上角「···」，选择「开具交易流水证明」；',
        '用途选择「个人借款／签证等业务」（不要选报销），选择时间范围；',
        '填写本人邮箱，支付宝会把加密文件发送到该邮箱；',
        '解压密码会通过短信发送到账号绑定的手机号，请记下来；',
        '到邮箱中下载附件（iPhone 请先存储到「文件」App），然后回到本页上传。'
      ]
    }
  };

  var views = ['home', 'platform', 'guide', 'upload', 'done'];
  var stepOf = { home: 1, platform: 2, guide: 3, upload: 4, done: 4 };

  function $(id) { return document.getElementById(id); }

  function showView(name) {
    views.forEach(function (v) {
      $('view-' + v).classList.toggle('hidden', v !== name);
    });
    var current = stepOf[name];
    Array.prototype.forEach.call($('stepBar').children, function (li, i) {
      li.classList.toggle('active', i + 1 === current);
      li.classList.toggle('done', i + 1 < current || name === 'done');
    });
    window.scrollTo(0, 0);
  }

  function showError(message) {
    var box = $('formError');
    box.textContent = message;
    box.classList.remove('hidden');
  }

  function clearError() {
    $('formError').classList.add('hidden');
  }

  function resetProgress() {
    $('progress').classList.add('hidden');
    $('progressText').classList.add('hidden');
    $('progressBar').style.width = '0%';
  }

  // 第 1 步：授权
  $('consentCheck').addEventListener('change', function () {
    $('btnStart').disabled = !this.checked;
  });
  $('btnStart').addEventListener('click', function () {
    showView('platform');
  });

  // 第 2 步：平台
  Array.prototype.forEach.call(document.querySelectorAll('.platform'), function (btn) {
    btn.addEventListener('click', function () {
      state.platform = btn.getAttribute('data-platform');
      var guide = guides[state.platform];
      $('guideTitle').textContent = guide.title;
      $('guideSteps').innerHTML = guide.steps
        .map(function (s) { return '<li>' + s + '</li>'; })
        .join('');
      showView('guide');
    });
  });
  $('btnBackPlatform').addEventListener('click', function () {
    showView('platform');
  });
  $('btnToUpload').addEventListener('click', function () {
    clearError();
    showView('upload');
  });

  // 第 4 步：文件选择
  $('fileInput').addEventListener('change', function () {
    clearError();
    var file = this.files && this.files[0];
    var box = $('fileBox');
    if (!file) {
      box.classList.remove('has-file');
      $('fileText').innerHTML = '点击选择流水文件<br><small>支持 zip / pdf / xlsx / xls</small>';
      return;
    }
    var ext = (file.name.split('.').pop() || '').toLowerCase();
    if (ALLOWED_EXT.indexOf(ext) === -1) {
      this.value = '';
      box.classList.remove('has-file');
      $('fileText').innerHTML = '点击选择流水文件<br><small>支持 zip / pdf / xlsx / xls</small>';
      showError('文件格式不支持，请上传 zip / pdf / xlsx / xls 格式的流水文件');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      this.value = '';
      box.classList.remove('has-file');
      $('fileText').innerHTML = '点击选择流水文件<br><small>支持 zip / pdf / xlsx / xls</small>';
      showError('文件超过 ' + MAX_MB + 'MB 上限，请重新导出较短时间段的流水');
      return;
    }
    box.classList.add('has-file');
    var sizeText = file.size >= 1024 * 1024
      ? (file.size / 1024 / 1024).toFixed(1) + ' MB'
      : (file.size / 1024).toFixed(1) + ' KB';
    $('fileText').innerHTML = file.name + '（' + sizeText + '）<br><small>点击可重新选择</small>';
  });

  // 密码明文切换
  $('eyeBtn').addEventListener('click', function () {
    var input = $('password');
    var show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    this.textContent = show ? '隐藏' : '显示';
  });

  // 提交
  $('uploadForm').addEventListener('submit', function (event) {
    event.preventDefault();
    clearError();

    var file = $('fileInput').files && $('fileInput').files[0];
    if (!file) { showError('请先选择要上传的流水文件'); return; }
    var password = $('password').value;
    if (!password || password.length > 64) { showError('请填写文件解压密码（1-64 个字符）'); return; }
    var name = $('name').value.trim();
    if (name.length < 2 || name.length > 30) { showError('请填写客户姓名（2-30 个字符）'); return; }
    var phone = $('phone').value.trim();
    if (!/^1\d{10}$/.test(phone)) { showError('请填写正确的 11 位手机号'); return; }
    var orderNo = $('orderNo').value.trim();
    if (orderNo.length > 32) { showError('业务单号过长（最多 32 个字符）'); return; }

    var fd = new FormData();
    fd.append('file', file);
    fd.append('password', password);
    fd.append('platform', state.platform);
    fd.append('name', name);
    fd.append('phone', phone);
    fd.append('order_no', orderNo);

    var btn = $('btnSubmit');
    btn.disabled = true;
    btn.textContent = '提交中…';
    $('progress').classList.remove('hidden');
    $('progressText').classList.remove('hidden');

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/submissions');
    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) {
        var percent = Math.round((e.loaded / e.total) * 100);
        $('progressBar').style.width = percent + '%';
        $('progressText').textContent = '上传中 ' + percent + '%';
      }
    };
    xhr.onload = function () {
      var data = {};
      try { data = JSON.parse(xhr.responseText); } catch (e) { /* 保持空对象 */ }
      if (xhr.status === 200 && data.ok) {
        $('submissionId').textContent = '提交编号：' + (data.submission_id || '');
        showView('done');
      } else {
        showError(data.error || '提交失败（' + xhr.status + '），请稍后重试');
      }
      finish();
    };
    xhr.onerror = function () {
      showError('网络异常，请检查网络后重试');
      finish();
    };
    function finish() {
      btn.disabled = false;
      btn.textContent = '提交';
      resetProgress();
    }
    xhr.send(fd);
  });

  // 再提交一份：保留客户信息，清空文件与密码
  $('btnAgain').addEventListener('click', function () {
    $('fileInput').value = '';
    $('fileBox').classList.remove('has-file');
    $('fileText').innerHTML = '点击选择流水文件<br><small>支持 zip / pdf / xlsx / xls</small>';
    $('password').value = '';
    clearError();
    showView('platform');
  });

  showView('home');
})();
