data "aws_availability_zones" "available" {
	state = "available"
}

resource "aws_vpc" "main" {
	cidr_block           = var.vpc_cidr
	enable_dns_support   = true
	enable_dns_hostnames = true
	tags = {
		Name = "${var.project}-${var.environment}-vpc"
	}
}

resource "aws_internet_gateway" "igw" {
	vpc_id = aws_vpc.main.id
	tags = {
		Name = "${var.project}-${var.environment}-igw"
	}
}

resource "aws_subnet" "public" {
	count                   = 2
	vpc_id                  = aws_vpc.main.id
	cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
	availability_zone       = data.aws_availability_zones.available.names[count.index]
	map_public_ip_on_launch = true
	tags = {
		Name = "${var.project}-${var.environment}-public-${count.index}"
	}
}

resource "aws_subnet" "private" {
	count             = 2
	vpc_id            = aws_vpc.main.id
	cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
	availability_zone = data.aws_availability_zones.available.names[count.index]
	tags = {
		Name = "${var.project}-${var.environment}-private-${count.index}"
	}
}

resource "aws_route_table" "public" {
	vpc_id = aws_vpc.main.id
	route {
		cidr_block = "0.0.0.0/0"
		gateway_id = aws_internet_gateway.igw.id
	}
	tags = {
		Name = "${var.project}-${var.environment}-public-rt"
	}
}

resource "aws_route_table_association" "public" {
	count          = length(aws_subnet.public)
	subnet_id      = aws_subnet.public[count.index].id
	route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "ec2" {
	name        = "${var.project}-${var.environment}-ec2-sg"
	description = "SG for EC2 host"
	vpc_id      = aws_vpc.main.id

	ingress {
		from_port   = 80
		to_port     = 80
		protocol    = "tcp"
		cidr_blocks = ["0.0.0.0/0"]
	}
	ingress {
		from_port   = 443
		to_port     = 443
		protocol    = "tcp"
		cidr_blocks = ["0.0.0.0/0"]
	}
	egress {
		from_port   = 0
		to_port     = 0
		protocol    = "-1"
		cidr_blocks = ["0.0.0.0/0"]
	}

	tags = {
		Name = "${var.project}-${var.environment}-ec2-sg"
	}
}
