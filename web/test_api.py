"""
Simple test script for the Web API
Run this to verify the API is working correctly
"""

import requests
import time
import os

BASE_URL = "http://localhost:8000"


def test_health():
    """Test root endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    print("✓ Health check passed")
    return response.json()


def test_upload(file_path):
    """Test file upload"""
    print(f"Testing upload with {file_path}...")

    if not os.path.exists(file_path):
        print(f"✗ Test file not found: {file_path}")
        return None

    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
        response = requests.post(f"{BASE_URL}/api/upload", files=files)

    assert response.status_code == 200
    result = response.json()
    print(f"✓ Upload successful, task_id: {result['task_id']}")
    return result


def test_process(task_id, mode="sttn", skip_detection=True):
    """Test processing start"""
    print(f"Testing process start for task {task_id}...")

    payload = {
        "task_id": task_id,
        "mode": mode,
        "skip_detection": skip_detection
    }

    response = requests.post(f"{BASE_URL}/api/process", json=payload)
    assert response.status_code == 200
    result = response.json()
    print(f"✓ Processing started: {result['status']}")
    return result


def test_status(task_id):
    """Test status endpoint"""
    print(f"Testing status for task {task_id}...")

    response = requests.get(f"{BASE_URL}/api/status/{task_id}")
    assert response.status_code == 200
    result = response.json()
    print(f"✓ Status: {result['status']}, Progress: {result['progress']}%")
    return result


def test_download(task_id, output_path="output.mp4"):
    """Test download endpoint"""
    print(f"Testing download for task {task_id}...")

    response = requests.get(f"{BASE_URL}/api/download/{task_id}")

    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"✓ Downloaded to {output_path}")
        return True
    else:
        print(f"✗ Download failed: {response.status_code}")
        return False


def run_full_test(video_path):
    """Run full end-to-end test"""
    print("\n" + "=" * 50)
    print("Running Full API Test")
    print("=" * 50 + "\n")

    try:
        # 1. Health check
        health = test_health()
        print(f"API Version: {health.get('version', 'unknown')}\n")

        # 2. Upload
        upload_result = test_upload(video_path)
        if not upload_result:
            return False

        task_id = upload_result['task_id']
        print()

        # 3. Start processing
        process_result = test_process(task_id)
        print()

        # 4. Monitor progress
        print("Monitoring progress...")
        while True:
            status = test_status(task_id)

            if status['status'] == 'completed':
                print("✓ Processing completed!")
                break
            elif status['status'] == 'error':
                print(f"✗ Processing failed: {status.get('message', 'unknown error')}")
                return False

            time.sleep(2)

        print()

        # 5. Download result
        test_download(task_id, f"test_output_{task_id}.mp4")

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        # Default test video path
        video_path = "../../test/test.mp4"

    print(f"Using test video: {video_path}")
    success = run_full_test(video_path)
    sys.exit(0 if success else 1)
