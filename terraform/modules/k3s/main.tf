resource "aws_instance" "k3s_master" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t2.micro"
  subnet_id     = var.subnet_id
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.k3s.id]

  user_data = templatefile("${path.module}/scripts/k3s-master.sh", {
    node_token = random_password.k3s_token.result
  })

  tags = {
    Name        = "${var.cluster_name}-master"
    Environment = var.environment
  }
}

resource "aws_instance" "k3s_worker" {
  count         = var.worker_count
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t2.micro"
  subnet_id     = var.subnet_id
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.k3s.id]

  user_data = templatefile("${path.module}/scripts/k3s-worker.sh", {
    master_ip   = aws_instance.k3s_master.private_ip
    node_token  = random_password.k3s_token.result
  })

  tags = {
    Name        = "${var.cluster_name}-worker-${count.index + 1}"
    Environment = var.environment
  }
}

resource "random_password" "k3s_token" {
  length  = 32
  special = false
}

resource "aws_security_group" "k3s" {
  name        = "${var.cluster_name}-k3s-sg"
  description = "Security group for k3s cluster"
  vpc_id      = var.vpc_id

  # Allow all internal traffic
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }

  # Allow SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow Kubernetes API server
  ingress {
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.cluster_name}-k3s-sg"
    Environment = var.environment
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Output the kubeconfig command
output "kubeconfig_command" {
  value = "ssh ubuntu@${aws_instance.k3s_master.public_ip} 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed 's/127.0.0.1/${aws_instance.k3s_master.public_ip}/g' > k3s.yaml"
} 