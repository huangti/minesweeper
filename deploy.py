#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Deployment Script for Minesweeper (ms.505250.xyz)
Deploys static assets (including HTML, favicon.svg, favicon.ico) directly to Cloudflare Workers with Custom Domain.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
import ssl

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTNAME = "ms.505250.xyz"
ZONE_NAME = "505250.xyz"
WORKER_NAME = "minesweeper"

STATIC_FILES = {
    "/": ("public/index.html", "text/html; charset=utf-8", False),
    "/index.html": ("public/index.html", "text/html; charset=utf-8", False),
    "/minesweeper.html": ("public/minesweeper.html", "text/html; charset=utf-8", False),
    "/favicon.svg": ("public/favicon.svg", "image/svg+xml; charset=utf-8", False),
    "/favicon.ico": ("public/favicon.ico", "image/x-icon", True),
    "/apple-touch-icon.png": ("public/apple-touch-icon.png", "image/png", True),
}


def build_worker_script():
    """Generates the single-file Cloudflare Worker script containing all assets."""
    print("📦 正在打包前端资源与 Favicon 资源...")
    assets = {}
    for route, (rel_path, mime, is_binary) in STATIC_FILES.items():
        file_path = os.path.join(PROJECT_DIR, rel_path)
        if not os.path.exists(file_path):
            # Check fallback in project root
            fallback = os.path.join(PROJECT_DIR, os.path.basename(rel_path))
            if os.path.exists(fallback):
                file_path = fallback

        if not os.path.exists(file_path):
            print(f"⚠️ 警告: 资源文件未找到: {rel_path}")
            continue

        if is_binary:
            with open(file_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("ascii")
            assets[route] = {
                "content": content,
                "type": mime,
                "is_binary": True
            }
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            assets[route] = {
                "content": content,
                "type": mime,
                "is_binary": False
            }

    assets_json = json.dumps(assets)

    worker_code = f"""// Cloudflare Worker for Minesweeper
// Custom Domain: {HOSTNAME}
const ASSETS = {assets_json};

function base64ToUint8Array(base64) {{
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {{
    bytes[i] = binaryString.charCodeAt(i);
  }}
  return bytes;
}}

export default {{
  async fetch(request, env, ctx) {{
    const url = new URL(request.url);
    const path = url.pathname;

    // Handle CORS Preflight
    if (request.method === "OPTIONS") {{
      return new Response(null, {{
        status: 204,
        headers: {{
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Max-Age": "86400"
        }}
      }});
    }}

    // Static Assets
    const asset = ASSETS[path] || (path === "" ? ASSETS["/"] : null);
    if (asset) {{
      const isHtml = path.endsWith(".html") || path === "/" || path === "";
      const headers = {{
        "Content-Type": asset.type,
        "Cache-Control": isHtml ? "public, max-age=0, must-revalidate" : "public, max-age=86400",
        "Access-Control-Allow-Origin": "*"
      }};

      if (asset.is_binary) {{
        return new Response(base64ToUint8Array(asset.content), {{ headers }});
      }} else {{
        return new Response(asset.content, {{ headers }});
      }}
    }}

    // Fallback to index.html
    return new Response(ASSETS["/"].content, {{
      headers: {{
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "public, max-age=0, must-revalidate",
        "Access-Control-Allow-Origin": "*"
      }}
    }});
  }}
}};
"""
    print(f"✅ Worker 打包完成，总大小: {len(worker_code.encode('utf-8')) / 1024:.2f} KB")
    return worker_code


class CloudflareClient:
    def __init__(self, api_token=None, api_key=None, api_email=None):
        self.api_token = api_token
        self.api_key = api_key
        self.api_email = api_email
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.ctx = ssl.create_default_context()

    def _get_headers(self, content_type="application/json"):
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.api_key and self.api_email:
            headers["X-Auth-Key"] = self.api_key
            headers["X-Auth-Email"] = self.api_email
        return headers

    def request(self, method, path, data=None, content_type="application/json"):
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        body = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode("utf-8")
            elif isinstance(data, str):
                body = data.encode("utf-8")
            elif isinstance(data, bytes):
                body = data

        req = urllib.request.Request(url, data=body, headers=self._get_headers(content_type), method=method)
        try:
            with urllib.request.urlopen(req, context=self.ctx) as response:
                res_body = response.read().decode("utf-8")
                return json.loads(res_body)
        except urllib.error.HTTPError as e:
            err_content = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_content)
                err_msg = ", ".join([err.get("message", "") for err in err_json.get("errors", [])])
                raise RuntimeError(f"Cloudflare API 错误 ({e.code}): {err_msg or err_content}")
            except json.JSONDecodeError:
                raise RuntimeError(f"Cloudflare HTTP 错误 ({e.code}): {err_content}")

    def get_account_id(self):
        print("🔍 正在获取 Cloudflare 账户信息...")
        res = self.request("GET", "/accounts")
        accounts = res.get("result", [])
        if not accounts:
            raise RuntimeError("未找到可用的 Cloudflare 账户，请检查 Token 权限。")
        acc = accounts[0]
        print(f"✅ 找到账户: {acc.get('name')} (ID: {acc.get('id')})")
        return acc.get("id")

    def get_zone_id(self, domain_name):
        print(f"🔍 正在查询域名 {domain_name} 的 Zone 信息...")
        res = self.request("GET", f"/zones?name={domain_name}")
        zones = res.get("result", [])
        if not zones:
            raise RuntimeError(f"在您的账户下未找到域名 {domain_name}，请确认该域名已添加至 Cloudflare。")
        zone = zones[0]
        print(f"✅ 找到 Zone: {zone.get('name')} (ID: {zone.get('id')})")
        return zone.get("id")

    def upload_worker(self, account_id, script_name, script_code):
        print(f"🚀 正在上传 Worker: {script_name}...")
        boundary = "----WebKitFormBoundaryWorkerDeploy7MA4YWxkTrZu0gW"
        
        metadata = {
            "main_module": "worker.js",
            "compatibility_date": "2024-10-01"
        }
        
        parts = []
        # Metadata part
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(b'Content-Disposition: form-data; name="metadata"\r\n')
        parts.append(b'Content-Type: application/json\r\n\r\n')
        parts.append(json.dumps(metadata).encode("utf-8"))
        parts.append(b"\r\n")

        # Worker script part
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n')
        parts.append(b'Content-Type: application/javascript+module\r\n\r\n')
        parts.append(script_code.encode("utf-8"))
        parts.append(b"\r\n")

        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)

        content_type = f"multipart/form-data; boundary={boundary}"
        res = self.request("PUT", f"/accounts/{account_id}/workers/scripts/{script_name}", data=body, content_type=content_type)
        print("✅ Worker 上传成功！")
        return res

    def bind_custom_domain(self, account_id, zone_id, script_name, hostname):
        print(f"🌐 正在确认自定义域名 {hostname} 绑定至 Worker {script_name}...")
        data = {
            "zone_id": zone_id,
            "hostname": hostname,
            "service": script_name,
            "environment": "production"
        }
        try:
            res = self.request("PUT", f"/accounts/{account_id}/workers/domains", data=data)
            print(f"✅ 自定义域名 {hostname} 绑定成功！")
            return res
        except Exception as e:
            # Check existing domains
            try:
                domains_res = self.request("GET", f"/accounts/{account_id}/workers/domains")
                for d in domains_res.get("result", []):
                    if d.get("hostname") == hostname and d.get("service") == script_name:
                        print(f"ℹ️ 自定义域名 {hostname} 已绑定至 Worker {script_name}")
                        return d
            except Exception:
                pass
            print(f"⚠️ 绑定自定义域名提示: {e}")
            return None


def deploy(api_token=None, api_key=None, api_email=None):
    client = CloudflareClient(api_token=api_token, api_key=api_key, api_email=api_email)
    account_id = client.get_account_id()
    zone_id = client.get_zone_id(ZONE_NAME)
    script_code = build_worker_script()
    client.upload_worker(account_id, WORKER_NAME, script_code)
    client.bind_custom_domain(account_id, zone_id, WORKER_NAME, HOSTNAME)

    print("\n" + "=" * 60)
    print("🎉 恭喜！扫雷项目已成功部署到 Cloudflare！")
    print(f"🔗 访问地址: https://{HOSTNAME}")
    print("💡 Cloudflare 边缘节点已刷新，包含全新的 Favicon。")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    key = os.environ.get("CLOUDFLARE_API_KEY")
    email = os.environ.get("CLOUDFLARE_EMAIL")

    if not token and not (key and email):
        if len(sys.argv) > 1:
            token = sys.argv[1]
        else:
            candidates = [
                os.path.join(PROJECT_DIR, ".cf-token"),
                os.path.expanduser("~/.config/cloudflare/token")
            ]
            for c_path in candidates:
                if os.path.exists(c_path):
                    with open(c_path, "r", encoding="utf-8") as f:
                        token = f.read().strip()
                        if token:
                            break

        if not token and not (key and email):
            print("请输入 Cloudflare API Token (或设置环境变量 CLOUDFLARE_API_TOKEN):")
            try:
                token = input().strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(1)

    if not token and not (key and email):
        print("❌ 未提供 Cloudflare API Token 或 Global Key")
        sys.exit(1)

    try:
        deploy(api_token=token, api_key=key, api_email=email)
    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        sys.exit(1)
