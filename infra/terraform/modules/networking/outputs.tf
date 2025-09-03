output "vpc_id" {
	value = aws_vpc.main.id
}

output "public_subnet_ids" {
	value = [for s in aws_subnet.public : s.id]
}

output "private_subnet_ids" {
	value = [for s in aws_subnet.private : s.id]
}

output "ec2_sg_id" {
	value = aws_security_group.ec2.id
}
