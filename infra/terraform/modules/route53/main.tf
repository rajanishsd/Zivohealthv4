resource "aws_route53_zone" "zone" {
  name = var.zone_name
}

resource "aws_route53_record" "root_a" {
  zone_id = aws_route53_zone.zone.zone_id
  name    = var.zone_name
  type    = "A"
  ttl     = 60
  records = [var.target_ip]
}

resource "aws_route53_record" "www_a" {
  count   = var.create_www_record ? 1 : 0
  zone_id = aws_route53_zone.zone.zone_id
  name    = "www.${var.zone_name}"
  type    = "A"
  ttl     = 60
  records = [var.target_ip]
}

resource "aws_route53_record" "api_a" {
  zone_id = aws_route53_zone.zone.zone_id
  name    = "api.${var.zone_name}"
  type    = "A"
  ttl     = 60
  records = [var.target_ip]
}
