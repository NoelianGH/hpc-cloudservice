# Compute node untuk relawan-developer (disediakan platform, berjalan di head).
# Relawan login dari command prompt PC-nya:  ssh -p 2222 jd<id>@<alamat-head>
# Agen (agent.py, root) menarik daftar akses dari koordinator, membuat / menghapus user per
# jobdesk, dan meng-clone repo B hanya branch jobdesk itu. Push lewat gerbang git koordinator.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server git ca-certificates procps nano vim-tiny less curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd /var/lib/hpc-node \
    && groupadd relawan \
    # pam_loginuid gagal di dalam kontainer -> jadikan opsional agar login SSH tidak ditolak
    && sed -i 's/^session\s\+required\s\+pam_loginuid.so/session optional pam_loginuid.so/' /etc/pam.d/sshd \
    && rm -f /etc/ssh/ssh_host_*
COPY sshd_config /etc/ssh/sshd_config
COPY limits.conf /etc/security/limits.d/relawan.conf
COPY profile.sh /etc/profile.d/hpc-node.sh
COPY jobdesk /usr/local/bin/jobdesk
COPY agent.py /opt/hpc/agent.py
RUN chmod 755 /usr/local/bin/jobdesk && chmod 644 /etc/profile.d/hpc-node.sh
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 22
CMD ["python3", "-u", "/opt/hpc/agent.py"]
