# WireGuard Config Update Script

This guide explains how to install and configure the **`update_wg_config.sh`** script to update WireGuard configurations.

---

## 🚀 Installation Steps

### 1. Remove Existing Script (if present)

```bash
sudo rm /usr/local/bin/update_wg_config.sh
```

### 2. Move the New Script to `/usr/local/bin`

```bash
sudo mv update_wg_config.sh /usr/local/bin/
```

### 3. Set Permissions & Ownership

```bash
sudo chmod +x /usr/local/bin/update_wg_config.sh
sudo chown root:root /usr/local/bin/update_wg_config.sh
```

### 4. Configure `sudoers` for Password-less Execution

Open the sudoers file:

```bash
sudo visudo
```

Add the following line:

```plaintext
# WireGuard FastAPI Visco Setup
ec2-user(username from $whoami) ALL=(ALL) NOPASSWD: /usr/local/bin/update_wg_config.sh
```

---

## Contact Me

For any issues or queries, contact:

**Author:** Shiven Saini
**Email:** [shiven.career@proton.me](mailto:shiven.career@proton.me)
