import asyncio

import docker
import time
from typing import Dict, Any

class SecureExecutor:
    def __init__(self):
        # Khoi tao ket noi voi Docker daemon tren may
        self.client = docker.from_env()
    
    def _execute_sync(self, project_dir: str, timeout_seconds: int) -> Dict[str, Any]:
        container = None
        try:
            image, build_log = self.client.images.build(
                path=project_dir,
                rm=True,
                forcerm=True
            )
            
            container = self.client.containers.run(
                image.id,
                detach=True,
                mem_limit='256m',
                cpu_quota=50000,
                network_disabled=True
            )

            start_time = time.time()
            while container.status in ['created', 'running']:
                container.reload()
                if time.time() - start_time > timeout_seconds:
                    container.kill()
                    return {
                        "success": False, 
                        "stage": "runtime", 
                        "error": "Timeout", 
                        "logs": container.logs().decode('utf-8')
                    }
                time.sleep(0.5)

            result = container.wait()
            logs = container.logs().decode('utf-8')
            
            container.remove(force=True)

            return {
                "success": result['StatusCode'] == 0,
                "stage": "runtime",
                "exit_code": result['StatusCode'],
                "logs": logs
            }

        except docker.errors.BuildError as e:
            error_logs = "".join([chunk.get('stream', '') for chunk in e.build_log if 'stream' in chunk])
            return {
                "success": False,
                "stage": "build",
                "error": "Build failed",
                "logs": error_logs
            }
        except Exception as e:
            if container:
                container.remove(force=True)
            return {
                "success": False,
                "stage": "system",
                "error": str(e),
                "logs": ""
            }


    async def execute_from_root(self, project_dir: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        # Day tac vu dong bo sang thread pool
        return await asyncio.to_thread(
            self._execute_sync, 
            project_dir, 
            timeout_seconds
        )