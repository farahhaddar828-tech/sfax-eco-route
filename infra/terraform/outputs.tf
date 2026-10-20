output "public_ip" {
  value = aws_eip.node.public_ip
}

output "ssh" {
  value = "ssh ubuntu@${aws_eip.node.public_ip}"
}

output "fetch_kubeconfig" {
  description = "Run this, then: export KUBECONFIG=$PWD/kubeconfig"
  value       = "ssh ubuntu@${aws_eip.node.public_ip} 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed 's/127.0.0.1/${aws_eip.node.public_ip}/' > kubeconfig"
}

output "api_url" {
  value = "http://api.${aws_eip.node.public_ip}.nip.io"
}
