# LiYing 人像分割服务

此目录把 LiYing 的真实 `ImageProcessor` 封装成 `POST /v1/id-photo/segment`。请求字段为 `image`、`width`、`height`、`background`；响应返回 `imageBase64` 的透明 PNG，小程序会写入本地临时文件后继续裁切、换背景和排版。

本地验证使用 `models/unpacked/model/` 下的 `face_detection_yunet_2023mar.onnx`、`RMBG-1.4-model.onnx`、`yolov8n-pose.onnx`。云托管构建镜像时会从 LiYing 官方 v3.2.0 发布包下载并校验这三个模型，因此不应将模型文件提交到 GitHub。服务限制上传原图 10 MiB，并把输出最长边限制为 1600px，以控制小程序响应大小。

本地运行前设置 `LIYING_MODEL_DIR` 指向模型目录，再运行：

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:LIYING_MODEL_DIR = "$PWD\models\unpacked\model"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8080
```

云托管部署执行：

```powershell
.\tools\deploy-liying-cloudrun.ps1 -EnvId cloud1-d3gvuvekzb60ad8ac
```

部署完成后，在 `utils/photo-ai-client.js` 的 `PHOTO_AI_SEGMENT_ENDPOINT` 写入服务 HTTPS 地址加 `/v1/id-photo/segment`，并在微信公众平台将服务域名配置为 `uploadFile` 合法域名。

本服务包含并修改了 LiYing 的 AGPL-3.0 代码；线上向用户提供服务时，必须同时向服务用户提供本服务对应的完整源码和许可证。原始许可证见 `UPSTREAM-LICENSE-LiYing.txt`。

