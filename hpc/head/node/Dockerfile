# Compute node untuk relawan-developer (disediakan platform, berjalan di head).
# Relawan login dari command prompt PC-nya:  ssh -p 2222 jd<id>@<alamat-head>
# Agen (agent.py, root) menarik daftar akses dari koordinator, membuat / menghapus user per
# jobdesk, dan meng-clone repo B hanya branch jobdesk itu. Push lewat gerbang git koordinator.
# Perintah 'uji' menjalankan kontainer testing di Docker milik node ini (layanan dindN) lewat
# runner.py (root). CLI docker hanya bisa dipakai root (folder /opt/hpc/docker 0700).
ARG DOCKER_CLI_IMAGE=docker:27-cli
FROM ${DOCKER_CLI_IMAGE} AS dockercli

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server git ca-certificates procps nano vim-tiny less curl wget \
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
COPY --from=dockercli /usr/local/bin/docker /opt/hpc/docker/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-buildx /opt/hpc/docker/cli-plugins/docker-buildx
COPY uji /usr/local/bin/uji
COPY agent.py runner.py /opt/hpc/
RUN chmod 755 /usr/local/bin/jobdesk /usr/local/bin/uji && chmod 644 /etc/profile.d/hpc-node.sh \
    && chmod 700 /opt/hpc/docker && chmod 644 /opt/hpc/agent.py /opt/hpc/runner.py \
    && mkdir -p /run/hpc-docker && chmod 700 /run/hpc-docker
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 22
CMD ["python3", "-u", "/opt/hpc/agent.py"]
